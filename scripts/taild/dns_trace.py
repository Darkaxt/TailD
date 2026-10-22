"""Fixed Windows DNS Client private realtime trace. No global event-log changes.

Windows amd64 ABI from evntrace.h/evntcons.h/tdh.h. Only the installer-owned
reader uses this source. No arbitrary provider, session name or PID from IPC.
"""
from collections import deque
import ctypes as C
from ctypes import wintypes as W
import json
import ntpath
import os
import threading
import uuid

PROVIDER = '1c95126e-7eea-49a9-a3fe-a378b03ddb4d'


class TraceError(OSError):
    pass


def native_types():
    class GUID(C.Structure):
        _fields_=[('bytes',C.c_ubyte*16)]
    class WNODE(C.Structure):
        _fields_=[('BufferSize',W.ULONG),('ProviderId',W.ULONG),('HistoricalContext',C.c_ulonglong),
                  ('TimeStamp',C.c_longlong),('Guid',GUID),('ClientContext',W.ULONG),('Flags',W.ULONG)]
    class Properties(C.Structure):
        _fields_=[('Wnode',WNODE)]+[(n,W.ULONG) for n in
            ('BufferSize','MinimumBuffers','MaximumBuffers','MaximumFileSize','LogFileMode','FlushTimer',
             'EnableFlags','AgeLimit','NumberOfBuffers','FreeBuffers','EventsLost','BuffersWritten',
             'LogBuffersLost','RealTimeBuffersLost')]+[('LoggerThreadId',C.c_void_p),
                ('LogFileNameOffset',W.ULONG),('LoggerNameOffset',W.ULONG)]
    class Descriptor(C.Structure):
        _fields_=[('Id',W.USHORT),('Version',C.c_ubyte),('Channel',C.c_ubyte),('Level',C.c_ubyte),
                  ('Opcode',C.c_ubyte),('Task',W.USHORT),('Keyword',C.c_ulonglong)]
    class Header(C.Structure):
        _fields_=[('Size',W.USHORT),('HeaderType',W.USHORT),('Flags',W.USHORT),('EventProperty',W.USHORT),
                  ('ThreadId',W.ULONG),('ProcessId',W.ULONG),('TimeStamp',C.c_longlong),('ProviderId',GUID),
                  ('EventDescriptor',Descriptor),('ProcessorTime',C.c_ulonglong),('ActivityId',GUID)]
    class Record(C.Structure):
        _fields_=[('EventHeader',Header),('BufferContext',W.ULONG),('ExtendedDataCount',W.USHORT),
                  ('UserDataLength',W.USHORT),('ExtendedData',C.c_void_p),('UserData',C.c_void_p),('UserContext',C.c_void_p)]
    Callback=C.WINFUNCTYPE(None,C.POINTER(Record))
    class Logfile(C.Structure):
        # EVENT_TRACE and TRACE_LOGFILE_HEADER are unused output structures;
        # their Windows x64 sizes/alignment are fixed by the SDK ABI.
        _fields_=[('LogFileName',W.LPWSTR),('LoggerName',W.LPWSTR),('CurrentTime',C.c_longlong),
                  ('BuffersRead',W.ULONG),('ProcessTraceMode',W.ULONG),('CurrentEvent',C.c_ubyte*88),
                  ('LogfileHeader',C.c_ubyte*280),('BufferCallback',C.c_void_p),('BufferSize',W.ULONG),
                  ('Filled',W.ULONG),('EventsLost',W.ULONG),('EventRecordCallback',Callback),
                  ('IsKernelTrace',W.ULONG),('Context',C.c_void_p)]
    class Property(C.Structure):
        _fields_=[('PropertyName',C.c_ulonglong),('ArrayIndex',W.ULONG),('Reserved',W.ULONG)]
    if (C.sizeof(Properties),C.sizeof(Header),C.sizeof(Record),C.sizeof(Logfile))!=(120,80,112,448):
        raise TraceError('Unsupported Windows DNS trace ABI')
    return GUID,Properties,Record,Callback,Logfile,Property


class Trace:
    def __init__(self, owner_sid, *, capacity=8192):
        self.owner_sid=owner_sid
        self.session=str(uuid.uuid4())
        self.name='Darkaxt.TailD.DNS.'+self.session
        self.capacity=capacity
        self.lock=threading.Lock()
        self.events=deque(maxlen=capacity)
        self.sequence=0
        self.unknown=0
        self.errors=0
        self.state='stopped'
        self.thread=None
        self.handle=0
        self.consumer=None

    def start(self):
        if os.name!='nt' or C.sizeof(C.c_void_p)!=8:raise TraceError('Windows amd64 required')
        GUID,Properties,Record,Callback,Logfile,Property=native_types()
        self.types=(GUID,Properties,Record,Callback,Logfile,Property)
        self.api=C.WinDLL('advapi32',use_last_error=True)
        self.tdh=C.WinDLL('tdh',use_last_error=True)
        signatures={
            'StartTraceW':([C.POINTER(C.c_ulonglong),W.LPCWSTR,C.POINTER(Properties)],W.ULONG),
            'EnableTraceEx2':([C.c_ulonglong,C.POINTER(GUID),W.ULONG,C.c_ubyte,C.c_ulonglong,C.c_ulonglong,W.ULONG,C.c_void_p],W.ULONG),
            'OpenTraceW':([C.POINTER(Logfile)],C.c_ulonglong),
            'ProcessTrace':([C.POINTER(C.c_ulonglong),W.ULONG,C.c_void_p,C.c_void_p],W.ULONG),
            'ControlTraceW':([C.c_ulonglong,W.LPCWSTR,C.POINTER(Properties),W.ULONG],W.ULONG),
            'CloseTrace':([C.c_ulonglong],W.ULONG)}
        for name,(args,result) in signatures.items():
            f=getattr(self.api,name);f.argtypes=args;f.restype=result
        self.tdh.TdhGetPropertySize.argtypes=[C.POINTER(Record),W.ULONG,C.c_void_p,W.ULONG,C.POINTER(Property),C.POINTER(W.ULONG)]
        self.tdh.TdhGetPropertySize.restype=W.ULONG
        self.tdh.TdhGetProperty.argtypes=[C.POINTER(Record),W.ULONG,C.c_void_p,W.ULONG,C.POINTER(Property),W.ULONG,C.c_void_p]
        self.tdh.TdhGetProperty.restype=W.ULONG
        self.buffer=C.create_string_buffer(C.sizeof(Properties)+2048)
        self.properties=C.cast(self.buffer,C.POINTER(Properties))
        p=self.properties.contents
        p.Wnode.BufferSize=C.sizeof(self.buffer);p.Wnode.Flags=0x20000;p.Wnode.ClientContext=2
        p.BufferSize=64;p.MinimumBuffers=2;p.MaximumBuffers=16;p.LogFileMode=0x100
        p.LoggerNameOffset=C.sizeof(Properties)
        name=C.create_unicode_buffer(self.name)
        C.memmove(C.addressof(self.buffer)+p.LoggerNameOffset,name,C.sizeof(name))
        handle=C.c_ulonglong()
        error=self.api.StartTraceW(C.byref(handle),self.name,self.properties)
        if error:raise TraceError('DNS trace start rejected: '+str(error))
        self.handle=handle.value
        try:
            self.provider=GUID.from_buffer_copy(uuid.UUID(PROVIDER).bytes_le)
            error=self.api.EnableTraceEx2(self.handle,C.byref(self.provider),1,4,0,0,0,None)
            if error:raise TraceError('DNS provider enable rejected: '+str(error))
            self.callback=Callback(self._event)
            self.logfile=Logfile(LoggerName=self.name,ProcessTraceMode=0x10000100,EventRecordCallback=self.callback)
            value=self.api.OpenTraceW(C.byref(self.logfile))
            if value==0xffffffffffffffff:raise TraceError('DNS consumer open rejected')
            self.consumer=value
            self.state='observing'
            self.thread=threading.Thread(target=self._run,name='TailD private DNS trace')
            self.thread.start()
        except BaseException:
            self.close();raise

    def _run(self):
        handle=C.c_ulonglong(self.consumer)
        result=self.api.ProcessTrace(C.byref(handle),1,None,None)
        with self.lock:
            self.state='stopped' if result in (0,1223) else 'source-error'
            self.errors+=int(result not in (0,1223))

    def _property(self,record,name):
        Property=self.types[-1]
        text=C.create_unicode_buffer(name)
        descriptor=Property(C.addressof(text),0xffffffff,0)
        size=W.ULONG()
        error=self.tdh.TdhGetPropertySize(record,0,None,1,C.byref(descriptor),C.byref(size))
        if error or size.value>16384:raise TraceError('Unsupported DNS event property')
        value=C.create_string_buffer(size.value)
        if self.tdh.TdhGetProperty(record,0,None,1,C.byref(descriptor),size,value):
            raise TraceError('Unreadable DNS event property')
        return value.raw

    def _event(self,record):
        h=record.contents.EventHeader
        if bytes(h.ProviderId.bytes)!=uuid.UUID(PROVIDER).bytes_le or h.EventDescriptor.Id!=3008:return
        try:
            identity=process_identity(h.ProcessId,h.TimeStamp,self.owner_sid)
            if identity is None:
                with self.lock:self.unknown+=1
                return
            name=self._property(record,'QueryName').decode('utf-16-le').rstrip('\0')
            if not name or len(name)>253 or any(ord(c)<32 for c in name):raise TraceError('Invalid DNS query name')
            status=int.from_bytes(self._property(record,'QueryStatus'),'little')
            kind=int.from_bytes(self._property(record,'QueryType'),'little')
            results=self._property(record,'QueryResults').decode('utf-16-le').rstrip('\0')
            with self.lock:
                self.sequence+=1
                self.events.append({'sequence':self.sequence,'at':(h.TimeStamp-116444736000000000)//10,
                    'question':name,'type':kind,'status':status,'results':results[:8192],
                    'process':identity,'source':'windows-dns-client-3008'})
        except (OSError,ValueError,UnicodeError,OverflowError):
            with self.lock:self.errors+=1

    def read(self,after):
        with self.lock:
            oldest=self.events[0]['sequence'] if self.events else self.sequence+1
            events=[e for e in self.events if e['sequence']>after][:128]
            return {'session':self.session,'state':self.state,'sequence':events[-1]['sequence'] if events else self.sequence,
                    'latest_sequence':self.sequence,
                    'lost':max(0,oldest-after-1),'unassigned':self.unknown,'errors':self.errors,
                    'events':events,
                    'etw_events_lost':self.logfile.EventsLost if hasattr(self,'logfile') else 0}

    def close(self):
        if self.handle:
            result=self.api.ControlTraceW(self.handle,self.name,self.properties,1)
            if result not in (0,4201):raise TraceError('DNS trace stop rejected: '+str(result))
            self.handle=0
        if self.thread is not None:
            self.thread.join();self.thread=None
        if self.consumer is not None:
            self.api.CloseTrace(self.consumer);self.consumer=None
        self.state='stopped'


def process_identity(pid,event_filetime,owner_sid):
    """Capture path + creation time under one handle; never join a later reused PID."""
    import pywintypes,win32api,win32con,win32security
    handle=None
    try:
        handle=win32api.OpenProcess(0x1000,False,pid)
        token=win32security.OpenProcessToken(handle,win32con.TOKEN_QUERY)
        try:sid=win32security.ConvertSidToStringSid(win32security.GetTokenInformation(token,win32security.TokenUser)[0])
        finally:token.Close()
        if sid!=owner_sid:return None
        kernel=C.WinDLL('kernel32',use_last_error=True)
        kernel.GetProcessTimes.argtypes=[W.HANDLE]+[C.POINTER(W.FILETIME)]*4
        kernel.GetProcessTimes.restype=W.BOOL
        times=[W.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(int(handle),*[C.byref(t) for t in times]):return None
        ticks=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
        if ticks>event_filetime:return None
        kernel.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]
        kernel.QueryFullProcessImageNameW.restype=W.BOOL
        size=W.DWORD(32768);path=C.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(int(handle),0,path,C.byref(size)):
            return None
        return {'pid':pid,'created':ticks,'path':ntpath.normpath(path.value)}
    except (OSError,pywintypes.error):return None
    finally:
        if handle is not None:handle.Close()
