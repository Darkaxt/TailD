"""Owner-authenticated Windows pipe for fixed, read-only GlassWire operations.

No provider credentials, arbitrary paths, SQL, process launch, or source writes.
The installer/service owns elevation; this module never prompts or installs itself.
"""
import argparse
import json
import os
import re
import struct
import threading

import glasswire
import history

if os.name == 'nt':
    import pywintypes
    import win32api
    import win32con
    import win32event
    import win32file
    import win32pipe
    import win32security

REQUEST_BYTES = 65536
RESPONSE_BYTES = 16 * 1024 * 1024
# FILE_GENERIC_READ | FILE_GENERIC_WRITE without FILE_APPEND_DATA, which is
# FILE_CREATE_PIPE_INSTANCE on a pipe. Clients cannot create another instance.
CLIENT_ACCESS = 0x12019b


class ReaderError(glasswire.GlassWireError):
    def __init__(self, state='unavailable'):
        self.state = state
        super().__init__('Read-only reader ' + state)


def decode_message(raw, maximum=REQUEST_BYTES):
    if not isinstance(raw, bytes) or len(raw) > maximum:
        raise ReaderError('resource-limit')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result
    def reject(_):
        raise ValueError('nonfinite number')
    try:
        data = json.loads(raw, object_pairs_hook=pairs, parse_constant=reject)
        pending = [(data, 0)]
        count = 0
        while pending:
            value, depth = pending.pop()
            count += 1
            if depth > 24 or count > 1000000:
                raise ValueError('resource bound')
            if isinstance(value, dict):
                pending.extend((v, depth+1) for v in value.values())
            elif isinstance(value, list):
                pending.extend((v, depth+1) for v in value)
        return data
    except (ValueError, UnicodeError, RecursionError):
        raise ReaderError('invalid-message') from None


def current_sid():
    if os.name != 'nt':
        raise ReaderError('windows-required')
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    finally:
        token.Close()
    return win32security.ConvertSidToStringSid(sid)


def drop_unused_privileges():
    """Remove unnecessary privileges from this reader process, never its parent."""
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(),
        win32con.TOKEN_QUERY | win32con.TOKEN_ADJUST_PRIVILEGES)
    try:
        privileges = win32security.GetTokenInformation(token, win32security.TokenPrivileges)
        keep = {'SeChangeNotifyPrivilege','SeImpersonatePrivilege'}
        remove = [(luid,4) for luid,_ in privileges
                  if win32security.LookupPrivilegeName(None,luid) not in keep]  # SE_PRIVILEGE_REMOVED
        if remove:
            win32security.AdjustTokenPrivileges(token, False, remove)
        actual = win32security.GetTokenInformation(token, win32security.TokenPrivileges)
        if any(win32security.LookupPrivilegeName(None,luid) not in keep for luid,_ in actual):
            raise ReaderError('privilege-reduction-failed')
    finally:
        token.Close()


def pipe_name(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,96}', name):
        raise ReaderError('invalid-instance')
    return '\\\\.\\pipe\\Darkaxt.TailD.' + name


class GlassWireSource:
    """The privileged side alone discovers and resolves installed source paths."""
    def __init__(self, directory=None, *, owner_sid=None):
        # Explicit directory is for isolated verification. Production CLI does
        # not accept one; installer-provisioned source selection is not IPC input.
        self.directory = directory
        self.owner_sid=owner_sid
        self.dns_trace=None

    def after_disconnect(self):
        if self.dns_trace is not None:
            self.dns_trace.close();self.dns_trace=None

    def process_dns(self,request):
        if (set(request)!={'op','enabled','session','after'} or type(request['enabled']) is not bool or
            type(request['after']) is not int or not 0<=request['after']<=2**63-1 or
            request['session'] is not None and (not isinstance(request['session'],str) or
                not re.fullmatch('[a-f0-9-]{36}',request['session']))):raise ReaderError('invalid-command')
        if not self.owner_sid:raise ReaderError('denied')
        if not request['enabled']:
            if self.dns_trace is None:return {'state':'disabled','events':[]}
            self.dns_trace.close()
            result=self.dns_trace.read(request['after'] if request['session']==self.dns_trace.session else 0)
            result['state']='disabled'
            # Keep stopped observations until the owner's subsequent cursor
            # acknowledges its last committed batch. Never lose the final five
            # seconds merely because the user turned recording off.
            if request['session']==self.dns_trace.session and request['after']>=result['latest_sequence']:
                self.dns_trace=None
            return result
        import dns_trace
        if self.dns_trace is None:
            source=dns_trace.Trace(self.owner_sid)
            try:source.start()
            except OSError:raise ReaderError('dns-source-unavailable') from None
            self.dns_trace=source
        return self.dns_trace.read(request['after'] if request['session']==self.dns_trace.session else 0)

    def catalog(self):
        data = glasswire.discover(self.directory)
        main_identity = glasswire.physical_identity(data['main_database'])
        if len(data['databases']) > 4096:
            raise ReaderError('resource-limit')
        data['main_identity'] = main_identity
        for item in data['databases']:
            item['identity'] = glasswire.physical_identity(item['path']) if item['present'] else None
            item['reader_id'] = history.digest([item['path'], item['identity'], main_identity])
        return data

    def dispatch(self, request):
        if not isinstance(request, dict):
            raise ReaderError('invalid-command')
        if request.get('op')=='app-dns':return self.process_dns(request)
        if request == {'op':'catalog'}:
            return self.catalog()
        if set(request) != {'op','database','start','end','limit'} or request['op'] != 'traffic':
            raise ReaderError('invalid-command')
        if (not isinstance(request['database'], str) or
                not re.fullmatch('[a-f0-9]{64}', request['database']) or
                type(request['limit']) is not int or not 1 <= request['limit'] <= 10000):
            raise ReaderError('invalid-command')
        try:
            a, b = history.bounds(request['start'], request['end'])
        except history.HistoryError:
            raise ReaderError('invalid-window') from None
        if b-a > 86400 * 1000000:
            raise ReaderError('resource-limit')
        catalog = self.catalog()
        matches = [d for d in catalog['databases'] if d['present'] and d['reader_id'] == request['database']]
        if len(matches) != 1:
            raise ReaderError('source-changed')
        item = matches[0]
        result = glasswire.read_traffic(item['path'], catalog['main_database'],
                                        request['start'], request['end'], request['limit'])
        if result['generation'] != {'traffic_database':item['identity'],
                                    'application_database':catalog['main_identity']}:
            raise ReaderError('source-changed')
        result['source_version'] = catalog['version']
        return result


def _overlapped(handle, stop, operation):
    """One submitting thread owns the IO and cancellation through completion."""
    ov = pywintypes.OVERLAPPED()
    ov.hEvent = win32event.CreateEvent(None, True, False, None)
    try:
        try:
            value = operation(ov)
        except pywintypes.error as error:
            if error.winerror != 997:  # ERROR_IO_PENDING
                raise
            value = None
        # pywin32 ConnectNamedPipe returns these acceptable states, rather than
        # raising them. In particular, already-connected has no pending IO/event.
        if type(value) is int and value in (0, 535):
            return value, 0
        selected = win32event.WaitForMultipleObjects([ov.hEvent, stop], False, win32event.INFINITE)
        if selected == win32event.WAIT_OBJECT_0 + 1:
            # CancelIo is correct here: the same thread submitted this handle's
            # sole pending operation. Cancellation is not completion.
            win32file.CancelIo(handle)
            try:
                win32file.GetOverlappedResult(handle, ov, True)
            except pywintypes.error as error:
                if error.winerror != 995:  # ERROR_OPERATION_ABORTED
                    raise
            raise ReaderError('stopped')
        size = win32file.GetOverlappedResult(handle, ov, True)
        return value, size
    finally:
        win32api.CloseHandle(ov.hEvent)


def _read_exact(handle, stop, size):
    pieces = []
    while size:
        value, count = _overlapped(handle, stop, lambda ov: win32file.ReadFile(handle, size, ov))
        if count == 0 or value is None:
            raise ReaderError('disconnected')
        pieces.append(bytes(value[1][:count]))
        size -= count
    return b''.join(pieces)


def _receive(handle, stop, maximum):
    size = struct.unpack('!I', _read_exact(handle, stop, 4))[0]
    if not 0 < size <= maximum:
        raise ReaderError('resource-limit')
    return decode_message(_read_exact(handle, stop, size), maximum)


def _send(handle, stop, data, maximum):
    raw = json.dumps(data, separators=(',',':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(raw) > maximum:
        raise ReaderError('resource-limit')
    raw = struct.pack('!I', len(raw)) + raw
    while raw:
        _, count = _overlapped(handle, stop, lambda ov: win32file.WriteFile(handle, raw, ov))
        if not count:
            raise ReaderError('disconnected')
        raw = raw[count:]


def assemble_batch(terminal,events,expected_count=None):
    """Complete one acknowledged streamed revision, without a second large frame."""
    if not isinstance(terminal,dict) or 'streamed_results' not in terminal:return terminal
    count=terminal['streamed_results']
    if (type(count) is not int or not 1<=count<=16 or len(events)!=count
        or expected_count is not None and count!=expected_count):
        raise ReaderError('invalid-response')
    keys=('revision','aggregation_version','correlation_version')
    if any(key not in terminal for key in keys):raise ReaderError('invalid-response')
    results=[None]*count
    for event in events:
        if not isinstance(event,dict):raise ReaderError('invalid-response')
        index=event.get('index')
        if (type(index) is not int or not 0<=index<count or results[index] is not None
            or any(event.get(key)!=terminal[key] for key in keys)
            or not isinstance(event.get('result'),dict) or event['result'].get('revision')!=terminal['revision']):
            raise ReaderError('invalid-response')
        results[index]=event['result']
    return {**{key:terminal[key] for key in keys},'results':results}


class PipeServer:
    def __init__(self, name, owner_sid, source, *, ready_handle=None):
        if os.name != 'nt':
            raise ReaderError('windows-required')
        self.name = pipe_name(name)
        try:
            win32security.ConvertStringSidToSid(owner_sid)
        except pywintypes.error:
            raise ReaderError('invalid-owner') from None
        self.owner_sid = owner_sid
        self.source = source
        self.ready = threading.Event()
        self._stop = win32event.CreateEvent(None, True, False, None)
        self._handle = None
        self._closed = False
        self._lifecycle = threading.Lock()
        self._serving_ident = None
        self.stopped = threading.Event()
        self.ready_handle = ready_handle

    def stop(self):
        with self._lifecycle:
            if not self._closed:
                win32event.SetEvent(self._stop)

    def close(self):
        if self._serving_ident not in (None, threading.get_ident()) and not self.stopped.is_set():
            self.stop()
            self.stopped.wait()
            return
        with self._lifecycle:
            if not self._closed:
                self._closed = True
                if self._handle is not None:
                    win32api.CloseHandle(self._handle)
                    self._handle = None
                win32api.CloseHandle(self._stop)
                self.stopped.set()

    def _authenticate(self):
        impersonating = False
        try:
            win32security.ImpersonateNamedPipeClient(self._handle)
            impersonating = True
            token = win32security.OpenThreadToken(win32api.GetCurrentThread(), win32con.TOKEN_QUERY, True)
            try:
                sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
                actual = win32security.ConvertSidToStringSid(sid)
            finally:
                token.Close()
            if actual != self.owner_sid:
                raise ReaderError('denied')
        except pywintypes.error:
            raise ReaderError('denied') from None
        finally:
            if impersonating:
                # Always leave the client context before accessing source data.
                try:
                    win32security.RevertToSelf()
                except pywintypes.error:
                    raise SystemExit('Reader could not leave client identity') from None

    def serve(self):
        self._serving_ident = threading.get_ident()
        sd = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
            'D:P(A;;GA;;;SY)(A;;0x12019b;;;'+self.owner_sid+')',
            win32security.SDDL_REVISION_1)
        sa = pywintypes.SECURITY_ATTRIBUTES()
        sa.SECURITY_DESCRIPTOR = sd
        try:
            self._handle = win32pipe.CreateNamedPipe(self.name,
                win32pipe.PIPE_ACCESS_DUPLEX | win32file.FILE_FLAG_OVERLAPPED | 0x80000,
                win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT |
                win32pipe.PIPE_REJECT_REMOTE_CLIENTS, 1, 65536, 65536, 0, sa)
        except pywintypes.error:
            self.close()
            raise ReaderError('instance-unavailable') from None
        self.ready.set()
        if self.ready_handle is not None:
            win32event.SetEvent(self.ready_handle)
        try:
            while win32event.WaitForSingleObject(self._stop, 0) != win32event.WAIT_OBJECT_0:
                authenticated = False
                try:
                    try:
                        _overlapped(self._handle, self._stop,
                                    lambda ov: win32pipe.ConnectNamedPipe(self._handle, ov))
                    except pywintypes.error as error:
                        if error.winerror != 535:  # Already connected before ConnectNamedPipe
                            raise
                    while True:
                        request = _receive(self._handle, self._stop, REQUEST_BYTES)
                        self._authenticate()
                        authenticated = True
                        try:
                            def progress(data):
                                _send(self._handle,self._stop,{'ok':True,'progress':True,'data':data},RESPONSE_BYTES)
                                if _receive(self._handle,self._stop,REQUEST_BYTES)!={'op':'ack'}:
                                    raise ReaderError('invalid-message')
                            if isinstance(request,dict) and request.get('op')=='view-query' and hasattr(self.source,'dispatch_progress'):
                                result=self.source.dispatch_progress(request,progress)
                                # Every panel was already sent and acknowledged. Resending
                                # the entire batch can exceed the frame cap even though
                                # each panel fits. Keep the original terminal receipt.
                                result={**{key:result[key] for key in ('revision','aggregation_version','correlation_version')},
                                        'streamed_results':len(result['results'])}
                            else:result = {'state':'stopping'} if request == {'op':'shutdown'} else self.source.dispatch(request)
                            response = {'ok':True, 'data':result}
                        except ReaderError as error:
                            response = {'ok':False, 'state':error.state}
                        except glasswire.GlassWireError as error:
                            incompatible = str(error).startswith(('Unsupported','Incompatible','Invalid','Missing','Truncated'))
                            response = {'ok':False, 'state':'incompatible' if incompatible else 'source-unavailable'}
                        except OSError:
                            response = {'ok':False, 'state':'source-unavailable'}
                        _send(self._handle, self._stop, response, RESPONSE_BYTES)
                        # One collector retains one connection. Explicit receipt
                        # prevents discarding output on disconnect and keeps
                        # request ordering deterministic without reconnect races.
                        if _receive(self._handle, self._stop, REQUEST_BYTES) != {'op':'ack'}:
                            raise ReaderError('invalid-message')
                        if hasattr(self.source, 'after_receipt'):
                            self.source.after_receipt(request)
                        if request == {'op':'shutdown'}:
                            self.stop()
                            break
                except (ReaderError, pywintypes.error):
                    pass  # One failed client never triggers a source retry.
                finally:
                    try:
                        win32pipe.DisconnectNamedPipe(self._handle)
                    except pywintypes.error:
                        pass
                    if authenticated and hasattr(self.source,'after_disconnect'):
                        self.source.after_disconnect()
        finally:
            self.close()


class PipeClient:
    def __init__(self, name):
        if os.name != 'nt':
            raise ReaderError('windows-required')
        self.name = pipe_name(name)
        self._stop = win32event.CreateEvent(None, True, False, None)
        self._lock = threading.Lock()
        self._closed = False
        self._catalog = None
        self._handle = None

    def close(self):
        if not self._closed:
            win32event.SetEvent(self._stop)
            with self._lock:
                if not self._closed:
                    self._closed = True
                    if self._handle is not None:
                        win32api.CloseHandle(self._handle)
                        self._handle = None
                    win32api.CloseHandle(self._stop)

    def request(self, request,*,on_result=None):
        with self._lock:
            if self._closed:
                raise ReaderError('stopped')
            try:
                if self._handle is None:
                    self._handle = win32file.CreateFile(self.name, CLIENT_ACCESS, 0, None,
                        win32con.OPEN_EXISTING, win32file.FILE_FLAG_OVERLAPPED |
                        win32con.SECURITY_SQOS_PRESENT | 0x10000, None)  # SECURITY_IDENTIFICATION
                _send(self._handle, self._stop, request, REQUEST_BYTES)
                events=[]
                while True:
                    response = _receive(self._handle, self._stop, RESPONSE_BYTES)
                    _send(self._handle, self._stop, {'op':'ack'}, REQUEST_BYTES)
                    if not isinstance(response,dict) or response.get('progress') is not True:break
                    if response.get('ok') is not True or request.get('op')!='view-query':raise ReaderError('invalid-response')
                    events.append(response['data'])
                    if on_result:on_result(response['data'])
                if not isinstance(response, dict) or response.get('ok') is not True:
                    raise ReaderError(response.get('state','invalid-response') if isinstance(response,dict) else 'invalid-response')
                queries=request.get('body',{}).get('queries') if request.get('op')=='view-query' else None
                return assemble_batch(response['data'],events,len(queries) if isinstance(queries,list) else None)
            except (pywintypes.error, KeyError, TypeError):
                if self._handle is not None:
                    win32api.CloseHandle(self._handle)
                    self._handle = None
                raise ReaderError('unavailable') from None

    def discover(self, directory=None):
        if directory is not None:
            raise ReaderError('invalid-command')
        self._catalog = self.request({'op':'catalog'})
        return self._catalog

    def physical_identity(self, path):
        if self._catalog is None:
            raise ReaderError('catalog-required')
        if path == self._catalog['main_database']:
            return self._catalog['main_identity']
        for item in self._catalog['databases']:
            if path == item['path'] and item['present']:
                return item['identity']
        raise ReaderError('unknown-source')

    def read_traffic(self, stats_db, main_db, start, end, limit):
        if self._catalog is None or main_db != self._catalog['main_database']:
            raise ReaderError('unknown-source')
        items = [d for d in self._catalog['databases'] if d['path'] == stats_db and d['present']]
        if len(items) != 1:
            raise ReaderError('unknown-source')
        return self.request({'op':'traffic','database':items[0]['reader_id'],
                             'start':start,'end':end,'limit':limit})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance', required=True)
    parser.add_argument('--owner-sid', required=True)
    parser.add_argument('--ready-event', help='Owner-created lifecycle event for supervised launch')
    args = parser.parse_args(argv)
    drop_unused_privileges()
    ready_handle = None
    if args.ready_event:
        if args.ready_event != 'Local\\Darkaxt.TailD.Ready.'+args.instance:
            parser.error('ready event must be bound to the selected instance')
        ready_handle = win32event.OpenEvent(win32con.EVENT_MODIFY_STATE, False, args.ready_event)
    server = PipeServer(args.instance, args.owner_sid, GlassWireSource(owner_sid=args.owner_sid), ready_handle=ready_handle)
    try:
        server.serve()
    except KeyboardInterrupt:
        server.stop()
    finally:
        server.close()
        if ready_handle is not None:
            win32api.CloseHandle(ready_handle)


if __name__ == '__main__':
    main()
