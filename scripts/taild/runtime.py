"""Opt-in owning-user collector and authenticated local query lifecycle.

Run explicitly; no startup registration, installation, elevation, or VPN writes.
One worker owns SQLite writes and source acquisition. Native dashboard reads use
separate read-only connections and never wait for an unrelated source operation.
"""
import argparse
import asyncio
from collections import deque
from concurrent.futures import Future
from datetime import datetime, timezone
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import threading
import time

import analytics
import controld
import credentials
import desktop_api
import glasswire
import history
import ingestion
import lifecycle
import reader


class RuntimeError(reader.ReaderError):
    pass


DEFAULTS = {'traffic':False, 'dns':False, 'traffic_seconds':10, 'dns_seconds':60,
            'host_scope':'local-windows', 'provider':None}


def settings(value):
    if not isinstance(value, dict) or set(value)-set(DEFAULTS):
        raise RuntimeError('invalid-settings')
    result = {**DEFAULTS, **value}
    if any(type(result[k]) is not bool for k in ('traffic','dns')):
        raise RuntimeError('invalid-settings')
    for key, lower in (('traffic_seconds',10), ('dns_seconds',60)):
        if type(result[key]) is not int or not lower <= result[key] <= 86400:
            raise RuntimeError('invalid-settings')
    if not isinstance(result['host_scope'],str) or not 1 <= len(result['host_scope']) <= 128:
        raise RuntimeError('invalid-settings')
    provider = result['provider']
    if provider is not None:
        required = {'account_scope','endpoint','account_type','instance'}
        if not isinstance(provider,dict) or not required <= set(provider) or set(provider)-required-{'organization'}:
            raise RuntimeError('invalid-settings')
        try:
            for field in ('account_scope','endpoint'):
                controld._identifier(provider[field])
            controld._instance(provider['instance'])
        except controld.ControlDError:
            raise RuntimeError('invalid-settings') from None
        if provider['account_type'] not in ('personal','organization'):
            raise RuntimeError('invalid-settings')
        if provider.get('organization') is not None and (not isinstance(provider['organization'],str) or
                not 1 <= len(provider['organization']) <= 128):
            raise RuntimeError('invalid-settings')
    if result['dns'] and provider is None:
        raise RuntimeError('explicit-provider-required')
    return result


class LocalAPI:
    """Event-driven loopback query API with explicit owned-I/O cancellation."""
    def __init__(self, collector):
        self.collector = collector
        self.token = secrets.token_urlsafe(32)
        self.closed = False
        self.closing = False
        self.ready = threading.Event()
        self.error = None
        self.active = {}
        self.loop = asyncio.new_event_loop()
        self.server = None
        self.thread = threading.Thread(target=self._serve, name='TailD local API')
        self.thread.start()
        self.ready.wait()
        if self.error:
            self.thread.join()
            raise RuntimeError('local-api-unavailable')

    async def _start(self):
        self.server = await asyncio.start_server(self._request, '127.0.0.1', 0,
                                                 limit=reader.REQUEST_BYTES, backlog=4)
        self.port = self.server.sockets[0].getsockname()[1]
        self.origin = 'http://127.0.0.1:' + str(self.port)

    def _serve(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._start())
        except BaseException as error:
            self.error = type(error).__name__
            self.ready.set()
            self.loop.close()
            return
        self.ready.set()
        try:
            self.loop.run_forever()
        finally:
            self.loop.run_until_complete(self._shutdown())
            self.loop.close()

    async def _respond(self, writer, status, data):
        raw = json.dumps(ingestion.exact_json(data), separators=(',',':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
        if len(raw) > reader.RESPONSE_BYTES:
            status, raw = 413, b'{"state":"resource-limit"}'
        reason = {200:'OK',400:'Bad Request',403:'Forbidden',404:'Not Found',
                  413:'Payload Too Large'}[status]
        header = ('HTTP/1.1 '+str(status)+' '+reason+'\r\n'
                  'Content-Type: application/json; charset=utf-8\r\n'
                  'Content-Length: '+str(len(raw))+'\r\n'
                  'Cache-Control: no-store\r\n'
                  'X-Content-Type-Options: nosniff\r\n'
                  "Content-Security-Policy: default-src 'none'; frame-ancestors 'none'\r\n"
                  'Connection: close\r\n\r\n').encode('ascii')
        writer.write(header+raw)
        await writer.drain()

    async def _request(self, incoming, writer):
        task = asyncio.current_task()
        if self.closing or len(self.active) >= 4:
            writer.transport.abort()
            return
        self.active[task] = writer
        try:
            raw = await incoming.readuntil(b'\r\n\r\n')
            if len(raw) > reader.REQUEST_BYTES:
                raise RuntimeError('resource-limit')
            lines = raw.decode('ascii').split('\r\n')
            request = lines[0].split(' ')
            if len(request) != 3 or request[2] != 'HTTP/1.1':
                raise RuntimeError('invalid-http')
            if request[0] != 'POST' or request[1] not in ('/api/query','/api/state'):
                await self._respond(writer,404,{'state':'not-found'})
                return
            headers = {}
            for line in lines[1:-2]:
                if ':' not in line or line[0].isspace():
                    raise RuntimeError('invalid-http')
                key,value = line.split(':',1)
                if not key or not all(c.isascii() and (c.isalnum() or c=='-') for c in key):
                    raise RuntimeError('invalid-http')
                key = key.lower()
                if key in headers:
                    raise RuntimeError('invalid-http')
                headers[key] = value.strip()
            supplied = headers.get('authorization','')
            if (not hmac.compare_digest(supplied,'Bearer '+self.token) or
                    headers.get('origin') != self.origin or
                    headers.get('host') != self.origin.removeprefix('http://') or
                    headers.get('content-type') != 'application/json' or
                    headers.get('sec-fetch-site') not in (None,'same-origin') or
                    'transfer-encoding' in headers):
                await self._respond(writer,403,{'state':'denied'})
                return
            size = headers.get('content-length','')
            if not size.isdecimal() or not 0 < int(size) <= reader.REQUEST_BYTES:
                raise RuntimeError('resource-limit')
            body = reader.decode_message(await incoming.readexactly(int(size)))
            if request[1] == '/api/query':
                if not isinstance(body,dict) or set(body) != {'queries'}:
                    raise RuntimeError('invalid-query')
                future = self.collector.submit('query',body)
            else:
                if body != {}:
                    raise RuntimeError('invalid-query')
                future = self.collector.submit('state')
            # Canceling a disconnected HTTP request does not cancel or corrupt
            # an already queued/executing SQLite operation.
            result = await asyncio.shield(asyncio.wrap_future(future))
            await self._respond(writer,200,result)
        except asyncio.CancelledError:
            writer.transport.abort()
            raise
        except analytics.QueryError as error:
            if not self.closing:
                await self._respond(writer,413 if error.code=='resource-limit' else 400,
                    {'state':error.code,'hint':'narrow-interval-or-scope' if error.code=='resource-limit' else 'check-query-contract'})
        except (reader.ReaderError, history.HistoryError,
                ValueError, UnicodeError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            if not self.closing:
                try:
                    await self._respond(writer,400,{'state':'invalid-request'})
                except OSError:
                    pass
        except OSError:
            pass
        finally:
            self.active.pop(task,None)
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def _shutdown(self):
        if self.closed:
            return
        self.closing = True
        if self.server is not None:
            self.server.close()
            # Python 3.12.1+ wait_closed waits for clients too. Abort owned
            # transports before awaiting that state, including accepted peers
            # whose handler has not yet reached the active-task registration.
            self.server.abort_clients()
        active = list(self.active.items())
        for task,writer in active:
            writer.transport.abort()
            task.cancel()
        if active:
            await asyncio.gather(*(task for task,_ in active),return_exceptions=True)
        if self.server is not None:
            await self.server.wait_closed()
        self.closed = True
        self.token = ''

    def close(self):
        if self.closed or self.error:
            return
        asyncio.run_coroutine_threadsafe(self._shutdown(),self.loop).result()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()

class Collector:
    def __init__(self, directory, traffic_reader, *, now=None, instance='collector', cli=None):
        self.directory = Path(directory).absolute()
        self.reader = traffic_reader
        self.instance = instance
        self.cli = cli
        self.now = now or (lambda: datetime.now(timezone.utc).isoformat())
        self.condition = threading.Condition()
        self.queue = deque()
        self.ready = threading.Event()
        self.closed = threading.Event()
        self.thread = None
        self.store = None
        self.api = None
        self.mutex = None
        self.start_error = None
        self.closing = False
        self.paused = False
        self.write_error = False
        self.diagnostics = {'state':'not-published'}
        self.config = dict(DEFAULTS)
        self.sources = {'traffic':{'state':'disabled'}, 'dns':{'state':'disabled'},
                        'context':{'state':'not-configured' if cli is None else 'not-collected'}}
        self.not_before = {'traffic':0, 'dns':0}
        self._transient_token = None
        self.config_revision = 0
        self.coalesced_refresh = []
        self.lifecycle = None
        self.wake_pending = False
        self.stop_after_window_receipt = False
        self.window_attached = False

    def start(self):
        if self.thread is not None or self.closing:
            raise RuntimeError('invalid-lifecycle')
        if os.name != 'nt':
            raise RuntimeError('windows-required')
        # Object lifetime, not elapsed age or an abandoned mutex, excludes another
        # collector for this owner's exact storage path. No lock stealing.
        import win32api
        import win32event
        import win32security
        import pywintypes
        owner = reader.current_sid()
        token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), 8)  # TOKEN_QUERY
        try:
            if win32security.GetTokenInformation(token, win32security.TokenElevation):
                raise RuntimeError('unelevated-owner-required')
        finally:
            token.Close()
        sa = pywintypes.SECURITY_ATTRIBUTES()
        sa.SECURITY_DESCRIPTOR = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
            'D:P(A;;GA;;;SY)(A;;GA;;;'+owner+')', win32security.SDDL_REVISION_1)
        name = 'Local\\Darkaxt.TailD.Collector.' + history.digest([owner,str(self.directory.resolve()).casefold()])
        self.mutex = win32event.CreateMutex(sa, False, name)
        if win32api.GetLastError() == 183:
            win32api.CloseHandle(self.mutex)
            self.mutex = None
            raise RuntimeError('already-running')
        self.thread = threading.Thread(target=self._run, name='TailD owning-user collector')
        self.thread.start()
        self.ready.wait()
        if self.start_error:
            self.close()
            raise RuntimeError('startup-failed') from None
        try:
            self.api = LocalAPI(self)
            self.lifecycle = lifecycle.WindowsLifecycle(self._wake)
            self.lifecycle.start()
        except BaseException:
            self.close()
            raise

    def session(self):
        if self.api is None or self.closing:
            raise RuntimeError('unavailable')
        return {'origin':self.api.origin,'port':self.api.port,'token':self.api.token}

    def _wake(self, kind):
        with self.condition:
            if not self.closing:
                self.wake_pending = True
                self.condition.notify()

    def submit(self, op, body=None):
        future = Future()
        with self.condition:
            if self.closing or self.thread is None:
                raise RuntimeError('stopping')
            if len(self.queue) >= 32:
                raise RuntimeError('backpressure')
            self.queue.append((op,body or {},future))
            self.condition.notify()
        return future

    def command(self, op, body=None):
        return self.submit(op,body).result()

    def dispatch(self, request):
        if not isinstance(request,dict) or set(request)-{'op','body'} or 'op' not in request:
            raise RuntimeError('invalid-command')
        if request == {'op':'session'}:
            return self.session()
        if request == {'op':'shutdown'}:
            return {'state':'stopping'}
        if request['op'] not in ('state','configure','pause','resume','refresh','query','delete','cleanup','credential','credential-remove','window-opened','window-closed',*desktop_api.OPERATIONS):
            raise RuntimeError('invalid-command')
        try:
            op=request['op'];body=request.get('body') or {}
            if not isinstance(body,dict):raise RuntimeError('invalid-command')
            # The native pipe already serializes its caller. Read-only views do
            # not belong behind an unrelated source acquisition or write batch.
            # Lifecycle flags need no SQLite access; preserve explicit receipts.
            if op in ('state','window-opened','window-closed') and not body:
                with self.condition:
                    if self.closing:raise RuntimeError('stopping')
                    return self._execute(None,op,body)
            if op in ('view-query','view-catalog','export-query') or op=='saved-query' and body=={'action':'list'}:
                with self.condition:
                    if self.closing or self.store is None:raise RuntimeError('stopping')
                    store=self.store
                view=store.read_view(now=self.now())
                try:
                    if op=='view-catalog':view.db.execute('BEGIN')
                    return desktop_api.DesktopAPI(view).dispatch(op,body)
                finally:view.close()
            return self.command(request['op'], request.get('body'))
        except analytics.QueryError as error:
            # Typed-query validation failures are public protocol errors, not
            # fatal pipe-server exceptions or private exception messages.
            raise RuntimeError(error.code) from None
        except (sqlite3.Error,history.HistoryError):
            raise RuntimeError('unavailable') from None

    def after_receipt(self, request):
        if request == {'op':'shutdown'} or (request == {'op':'window-closed'} and self.stop_after_window_receipt):
            with self.condition:
                self.closing = True
                self.condition.notify()

    def after_disconnect(self):
        # The owning window can crash as well as close normally. An enabled
        # collector is intentionally independent; a disabled one has no consumer.
        if not self.closing and self.window_attached:
            try:
                self.command('window-closed')
                self.after_receipt({'op':'window-closed'})
            except reader.ReaderError:
                pass  # Worker already stopped; no new source operation.

    def _save_settings(self, value):
        target = self.directory/'runtime.json'
        staged = self.directory/'runtime.pending.json'
        if target.is_symlink() or staged.is_symlink():
            raise RuntimeError('invalid-storage')
        with staged.open('w', encoding='utf-8') as output:
            json.dump(value, output, separators=(',',':'))
            output.flush()
            os.fsync(output.fileno())
        staged.replace(target)

    def _state(self):
        enabled = [self.sources[k]['state'] for k in ('traffic','dns') if self.config[k]]
        state = ('stopping' if self.closing else 'write-error' if self.write_error else
                 'paused' if self.paused else 'disabled' if not enabled else
                 'collecting' if 'collecting' in enabled else 'starting' if 'starting' in enabled else 'stale')
        return {'state':state,'sources':json.loads(json.dumps(self.sources)),
                'queue_depth':len(self.queue),'settings':self.config,
                'lifecycle':self.lifecycle.status() if self.lifecycle is not None else {'state':'starting'},
                'credentials':'current-user-vault-optional','network_changes':False,
                'diagnostics':dict(self.diagnostics)}

    def _execute(self, store, op, body):
        if not isinstance(body,dict):
            raise RuntimeError('invalid-command')
        if op == 'state' and not body:
            return self._state()
        if op in desktop_api.OPERATIONS:
            if self.write_error and op in ('retention','saved-query','delete-snapshots') and body.get('action')!='list':
                raise RuntimeError('write-error')
            return desktop_api.DesktopAPI(store).dispatch(op,body)
        if op == 'credential-remove' and not body:
            credentials.CredentialStore().remove()
            self._transient_token=None
            self.config_revision+=1
            return {'removed':True,'provider_revocation':'not-performed'}
        if op == 'window-opened' and not body:
            self.window_attached = True
            self.stop_after_window_receipt = False
            return self._state()
        if op == 'window-closed' and not body:
            self.window_attached = False
            keep = self.config['traffic'] or self.config['dns']
            self.stop_after_window_receipt = not keep
            return {'collector_continues':keep,'state':self._state()['state']}
        if op == 'credential':
            if set(body) != {'token','confirm_read_only','persist'} or body['confirm_read_only'] is not True or type(body['persist']) is not bool:
                raise RuntimeError('read-only-confirmation-required')
            token = credentials.validate(body['token'])
            if body['persist']:
                credentials.CredentialStore().replace(token)
                self._transient_token = None
            else:
                self._transient_token = token
            self.config_revision += 1
            return {'configured':True,'storage':'user-vault' if body['persist'] else 'process-memory'}
        if op == 'configure':
            updated = settings({**self.config, **body})
            if updated == self.config:
                return self._state()
            self._save_settings(updated)
            previous = self.config
            self.config = updated
            self.config_revision += 1
            self.due = {'traffic':0, 'dns':0}
            for kind in ('traffic','dns'):
                if not self.config[kind]:
                    self.sources[kind] = {'state':'disabled'}
                elif not previous[kind]:
                    self.sources[kind] = {'state':'starting'}
            return self._state()
        if op in ('pause','resume') and not body:
            self.paused = op == 'pause'
            if op == 'resume':
                self.write_error = False
                self.due = {'traffic':0, 'dns':0}
                for kind in ('traffic','dns'):
                    if self.config[kind]:
                        self.sources[kind]['state'] = 'starting'
            return self._state()
        if op == 'query' and set(body) == {'queries'}:
            return analytics.Analytics(store).batch(body['queries'])
        if op == 'delete' and {'kind','start','end'} <= set(body) <= {'kind','start','end','source','application_path'}:
            if self.write_error:
                raise RuntimeError('write-error')
            store.delete(**body)
            return {'deleted':True,'replay_suppression':True}
        if op == 'cleanup' and not body:
            if self.write_error:
                raise RuntimeError('write-error')
            store.now = history.instant(self.now())
            store.cleanup()
            return {'retention_applied':True}
        if op == 'refresh' and not body:
            if not self.paused and not self.write_error:
                for kind in ('traffic','dns'):
                    if (not self.paused and not self.closing and not self.write_error and
                            self.config[kind] and time.monotonic() >= self.not_before[kind]):
                        self._acquire(store,kind, policy=kind == 'dns')
            return self._state()
        raise RuntimeError('invalid-command')

    def _acquire(self, store, kind, *, policy=False):
        committed_reads=0
        self.sources[kind] = {'state':'collecting','progress':{'phase':'discovering','committed_reads':0}}
        def report_progress(phase,left,right):
            nonlocal committed_reads
            if phase=='committed':committed_reads+=1
            self.sources[kind]={'state':'collecting','progress':{
                'phase':phase,'start':left,'end':right,'committed_reads':committed_reads}}
        retry = None
        revision = self.config_revision
        def checkpoint():
            # Source connections/transactions have already closed at these
            # boundaries. Serve queued queries and lifecycle operations before
            # starting another source slice, without aborting committed work.
            while True:
                with self.condition:
                    command = self.queue.popleft() if self.queue else None
                if command is None:
                    break
                if command[0] == 'refresh' and command[1] == {}:
                    self.coalesced_refresh.append((command[2],kind))
                else:
                    self._deliver(store,command)
            return not (self.closing or self.paused or self.write_error or
                        self.config_revision != revision or not self.config[kind])
        try:
            store.now = history.instant(self.now())
            store.cleanup()
            if self.cli is not None:
                try:
                    captured = analytics.capture_context(self.cli)
                    analytics.Analytics(store).record_context(self.config['host_scope'], captured)
                    self.sources['context'] = {'state':'point-observation','last_success_utc':self.now()}
                except analytics.QueryError:
                    self.sources['context'] = {'state':'unavailable','historical_binding':'unproven'}
            end = history.utc(store.now//1000000*1000000)
            start = store.health()['expiry_floor']
            if kind == 'traffic':
                result = ingestion.traffic_window(store, self.config['host_scope'],start,end,
                                                  reader=self.reader,checkpoint=checkpoint,progress=report_progress)
            else:
                provider = self.config['provider']
                token = self._transient_token or credentials.CredentialStore().read()
                if token is None:
                    raise RuntimeError('credential-required')
                try:
                    def fetch(left,right):
                        return controld.activity_slice(token,provider['account_type'],provider['instance'],left,right,
                            endpoint=provider['endpoint'],organization=provider.get('organization'),limit=1000)
                    # Eight requests prioritize the recent two-minute analytical
                    # overlap, then eight continue the captured retained-horizon
                    # backfill. These are resource budgets, not retries/timeouts.
                    recent_start = history.utc(max(history.instant(start),history.instant(end)-120*1000000))
                    recent = ingestion.dns_windows(store,provider['account_scope'],provider['endpoint'],
                        recent_start,end,fetch,max_slices=8,defer_budget=True,checkpoint=checkpoint,progress=report_progress)
                    progress = self._dns_progress(provider,start,end)
                    backfill = ({'slices_read':0,'pending_windows':progress['pending_windows'],'interrupted':True}
                                if recent.get('interrupted') else
                        ingestion.dns_windows(store,provider['account_scope'],provider['endpoint'],
                            progress['start'],progress['end'],fetch,max_slices=8,defer_budget=True,
                            resume_pending=progress['pending_windows'],checkpoint=checkpoint,progress=report_progress))
                    progress['pending_windows'] = backfill['pending_windows']
                    if not self.write_error:
                        self._save_dns_progress(progress)
                    result = {'slices_read':recent['slices_read']+backfill['slices_read'],
                              'request_budget':16,'recent_pending_windows':len(recent['pending_windows']),
                              'backfill_pending_windows':len(backfill['pending_windows']),
                              'interrupted':recent.get('interrupted',False) or backfill.get('interrupted',False)}
                    if policy and not result.get('interrupted') and checkpoint():
                        captured_policy = controld.policy_snapshot(token,provider['endpoint'],
                            account_scope=provider['account_scope'],organization=provider.get('organization'))
                        analytics.Analytics(store).record_policy(captured_policy)
                finally:
                    token = None
            if result.get('interrupted'):
                self.sources[kind] = {'state':'write-error' if self.write_error else 'paused' if self.paused else
                                      'disabled' if not self.config[kind] else 'starting','result':result}
            else:
                self.sources[kind] = {'state':'collecting','last_success_utc':self.now(),
                                      'result':result,'history_completeness':'inspect-query-coverage'}
        except controld.ControlDError as error:
            self.sources[kind] = {'state':error.state or 'stale','status':error.status}
            if error.retry_after is not None:
                self.sources[kind]['retry_after'] = error.retry_after
                if isinstance(error.retry_after,int):
                    retry = error.retry_after
                    until = history.utc(history.instant(self.now())+retry*1000000)
                else:
                    # The HTTP reader already normalized HTTP-date to RFC 3339
                    # UTC. Do not parse that ISO value again as an HTTP-date.
                    until = error.retry_after
                    retry = max(0,(history.instant(until)-history.instant(self.now()))/1000000)
                try:
                    self._save_provider_limit(until)
                except OSError:
                    self.write_error = True
        except reader.ReaderError as error:
            self.sources[kind] = {'state':error.state}
        except (glasswire.GlassWireError,credentials.CredentialError,history.HistoryError,analytics.QueryError):
            self.sources[kind] = {'state':'incompatible-or-unavailable'}
        except (sqlite3.Error,OSError):
            # SQLite transactions roll back their failed writes. Freeze further
            # writes until explicit resume; never advance a checkpoint or evict
            # private evidence to conceal disk exhaustion.
            self.write_error = True
            self.sources[kind] = {'state':'write-error'}
        finally:
            if retry:
                self.not_before[kind] = time.monotonic() + retry
            self.due[kind] = time.monotonic() + max(self.config[kind+'_seconds'],retry or 0)
            pending,self.coalesced_refresh = self.coalesced_refresh,[]
            for future,source in pending:
                if self.config_revision != revision and not (self.paused or self.closing or self.write_error):
                    with self.condition:
                        self.queue.appendleft(('refresh',{},future))
                else:
                    future.set_result({**self._state(),'refresh_coalesced_source':source})

    def _dns_progress(self, provider, start, end):
        path = self.directory/'runtime-dns-progress.json'
        scope = history.digest(provider)
        if path.exists():
            if path.is_symlink() or path.stat().st_nlink != 1 or path.stat().st_size > reader.REQUEST_BYTES:
                raise RuntimeError('invalid-dns-progress')
            value = reader.decode_message(path.read_bytes())
            if (not isinstance(value,dict) or set(value)!={'scope','start','end','pending_windows'} or
                    not isinstance(value['pending_windows'],list)):
                raise RuntimeError('invalid-dns-progress')
            a,b = history.bounds(value['start'],value['end'])
            if value['scope']==scope and value['pending_windows'] and b<=history.instant(end) and b>history.instant(start):
                return value
        return {'scope':scope,'start':start,'end':end,'pending_windows':[[start,end]]}

    def _save_dns_progress(self, value):
        pending = self.directory/'runtime-dns-progress.pending.json'
        target = self.directory/'runtime-dns-progress.json'
        if pending.is_symlink() or target.is_symlink():
            raise RuntimeError('invalid-dns-progress')
        raw = json.dumps(value,separators=(',',':'))
        if len(raw.encode())>reader.REQUEST_BYTES:
            raise RuntimeError('resource-limit')
        with pending.open('w',encoding='utf-8') as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        pending.replace(target)

    def _save_provider_limit(self, until):
        pending = self.directory/'runtime-provider-limit.pending.json'
        target = self.directory/'runtime-provider-limit.json'
        if pending.is_symlink() or target.is_symlink():
            raise RuntimeError('invalid-provider-limit')
        with pending.open('w',encoding='utf-8') as output:
            json.dump({'source':'http-retry-after','until_utc':until},output,separators=(',',':'))
            output.flush()
            os.fsync(output.fileno())
        pending.replace(target)

    def _restore_provider_limit(self):
        target = self.directory/'runtime-provider-limit.json'
        if not target.exists():
            return
        if target.is_symlink() or target.stat().st_nlink != 1 or target.stat().st_size>4096:
            raise RuntimeError('invalid-provider-limit')
        value = reader.decode_message(target.read_bytes())
        if not isinstance(value,dict) or set(value)!={'source','until_utc'} or value['source']!='http-retry-after':
            raise RuntimeError('invalid-provider-limit')
        remaining = max(0,(history.instant(value['until_utc'])-history.instant(self.now()))/1000000)
        self.not_before['dns'] = time.monotonic()+remaining
        if remaining and self.config['dns']:
            self.sources['dns'] = {'state':'rate-limited','retry_after_until':value['until_utc']}

    def _deliver(self, store, command):
        op,body,future = command
        try:
            future.set_result(self._execute(store,op,body))
        except (sqlite3.Error,OSError):
            self.write_error = True
            future.set_exception(RuntimeError('write-error'))
        except analytics.QueryError as error:
            future.set_exception(error)
        except reader.ReaderError as error:
            future.set_exception(error)
        except credentials.CredentialError:
            future.set_exception(RuntimeError('credential-not-accepted'))
        except (history.HistoryError,ValueError,TypeError):
            future.set_exception(RuntimeError('invalid-command'))
        except BaseException:
            # A programming defect terminates this worker, but must also settle
            # the command already removed from the queue. No silent retry.
            future.set_exception(RuntimeError('worker-failed'))
            raise

    def _diagnostic_status(self):
        source_status = {kind:{key:value for key,value in data.items()
                            if key in ('state','status','last_success_utc')}
                         for kind,data in self.sources.items()}
        data = {'version':'taild-runtime-v1','owner_pid':os.getpid(),
                'observed_at_utc':self.now(),'state':self._state()['state'],
                'sources':source_status,'queue_depth':len(self.queue)}
        pending = self.directory/'runtime-status.pending.json'
        target = self.directory/'runtime-status.json'
        if pending.is_symlink() or target.is_symlink():
            raise RuntimeError('invalid-storage')
        with pending.open('w', encoding='utf-8') as output:
            json.dump(data, output, separators=(',',':'))
            output.flush()
            os.fsync(output.fileno())
        pending.replace(target)

    def _publish_status(self):
        # Status is an observation channel, not the facts/checkpoint store. A
        # reader holding this JSON file must not turn an atomic rename conflict
        # into a history write failure or disable otherwise healthy acquisition.
        try:
            self._diagnostic_status()
        except OSError as error:
            self.diagnostics={'state':'unavailable','error_type':type(error).__name__,
                              'winerror':getattr(error,'winerror',None),'errno':error.errno}
        else:
            self.diagnostics={'state':'available'}

    def _run(self):
        store = None
        self.due = {'traffic':0, 'dns':0}
        try:
            store = history.History(self.directory, now=self.now())
            self.store = store
            saved = self.directory/'runtime.json'
            if saved.exists():
                if saved.is_symlink() or saved.stat().st_nlink != 1 or saved.stat().st_size > reader.REQUEST_BYTES:
                    raise RuntimeError('invalid-storage')
                self.config = settings(reader.decode_message(saved.read_bytes()))
            for kind in ('traffic','dns'):
                if self.config[kind]:
                    self.sources[kind]['state'] = 'starting'
            self._restore_provider_limit()
            self._publish_status()
            self.ready.set()
            while True:
                with self.condition:
                    if self.closing:
                        break
                    if self.wake_pending:
                        self.due = {'traffic':0,'dns':0}
                        self.wake_pending = False
                        self._restore_provider_limit()
                    command = self.queue.popleft() if self.queue else None
                    eligible = [] if self.paused or self.write_error else [k for k in ('traffic','dns') if self.config[k]]
                    due = [k for k in eligible if max(self.due[k],self.not_before[k]) <= time.monotonic()]
                    if command is None and not due:
                        # This wait schedules acquisition opportunities; expiry
                        # neither cancels nor classifies any running operation.
                        interval = min((max(self.due[k],self.not_before[k])-time.monotonic() for k in eligible),default=None)
                        self.condition.wait(None if interval is None else
                            min(threading.TIMEOUT_MAX,max(0,interval)))  # Native wait API limit only.
                        continue
                if command:
                    self._deliver(store,command)
                else:
                    self._acquire(store,due[0])
                self._publish_status()
        except BaseException as error:
            self.start_error = type(error).__name__
        finally:
            self.ready.set()
            with self.condition:
                self.closing = True
                while self.queue:
                    self.queue.popleft()[2].set_exception(RuntimeError('stopping'))
            if store is not None:
                store.close()
            self._transient_token = None
            self.closed.set()

    def close(self):
        with self.condition:
            self.closing = True
            self.condition.notify()
        if self.lifecycle is not None:
            self.lifecycle.close()
        if self.thread is not None:
            self.thread.join()
        if self.api is not None:
            self.api.close()
            self.api = None
        if self.mutex is not None:
            import win32api
            win32api.CloseHandle(self.mutex)
            self.mutex = None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run','state','pause','resume','refresh','shutdown','configure'), default='run', nargs='?')
    parser.add_argument('--history')
    parser.add_argument('--reader-instance')
    parser.add_argument('--cli', help='Installer-selected local TailDNS CLI for read-only context')
    parser.add_argument('--settings', help='Explicit nonsecret collection settings JSON for configure')
    parser.add_argument('--instance', default='collector')
    parser.add_argument('--ready-event', help='Owner-created event for supervised desktop startup')
    args = parser.parse_args(argv)
    if args.command != 'run':
        control_client = reader.PipeClient(args.instance)
        try:
            request = {'op':args.command}
            if args.command == 'configure':
                if not args.settings:
                    parser.error('configure requires --settings with explicit nonsecret settings')
                body = reader.decode_message(Path(args.settings).read_bytes())
                settings(body)
                request['body'] = body
            print(json.dumps(control_client.request(request)))
        finally:
            control_client.close()
        return
    if not args.history or not args.reader_instance:
        parser.error('run requires --history and --reader-instance')
    client = reader.PipeClient(args.reader_instance)
    collector = Collector(args.history, client, instance=args.instance, cli=args.cli)
    control = None
    thread = None
    update_stop = None
    try:
        if getattr(sys,'frozen',False):
            import maintenance
            update_stop=maintenance.StopEvent(collector,reader.current_sid(),args.instance)
        collector.start()
        ready_handle = None
        if args.ready_event:
            if args.ready_event != 'Local\\Darkaxt.TailD.Ready.'+args.instance:
                parser.error('ready event must be bound to the selected instance')
            import win32con, win32event
            ready_handle = win32event.OpenEvent(win32con.EVENT_MODIFY_STATE,False,args.ready_event)
        control = reader.PipeServer(args.instance, reader.current_sid(), collector,ready_handle=ready_handle)
        def serve_control():
            try:
                control.serve()
            finally:
                with collector.condition:
                    collector.closing = True
                    collector.condition.notify()
        thread = threading.Thread(target=serve_control, name='TailD owner control')
        thread.start()
        collector.closed.wait()
        control.stop()
        thread.join()
    finally:
        if control is not None:
            control.stop()
        collector.close()
        if update_stop is not None:
            update_stop.close()
        if thread is not None:
            thread.join()
        client.close()
        if 'ready_handle' in locals() and ready_handle is not None:
            import win32api
            win32api.CloseHandle(ready_handle)


if __name__ == '__main__':
    main()
