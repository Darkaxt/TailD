"""Owned Windows resume/interface notifications; no polling or visible window."""
import ctypes
from ctypes import wintypes
import os
import threading
import uuid

if os.name == 'nt':
    import win32api
    import win32con
    import win32gui


class WindowsLifecycle:
    def __init__(self, notify):
        self.notify = notify
        self.ready = threading.Event()
        self.thread = None
        self.hwnd = None
        self.registration = wintypes.HANDLE()
        self.error = None
        self.stopped = False
        self.counts = {'resume_events':0,'interface_events':0}
        self.lock = threading.Lock()
        self.callback = None
        self.api = None

    def status(self):
        with self.lock:
            return {'state':'stopped' if self.stopped else 'unavailable' if self.error else 'subscribed',
                    **self.counts,'native_error':self.error,'visibility':'never-shown'}

    def _notify(self, kind):
        with self.lock:
            self.counts[kind+'_events'] += 1
        self.notify(kind)

    def _window(self, hwnd, message, wparam, lparam):
        if message == win32con.WM_POWERBROADCAST:
            if wparam in (7,18):  # ResumeSuspend / ResumeAutomatic
                self._notify('resume')
            return 1
        if message == win32con.WM_CLOSE:
            win32gui.DestroyWindow(hwnd)
            return 0
        if message == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd,message,wparam,lparam)

    def _run(self):
        name = 'TailDCollectorLifecycle-' + uuid.uuid4().hex
        instance = win32api.GetModuleHandle(None)
        registered = False
        try:
            window_class = win32gui.WNDCLASS()
            window_class.hInstance = instance
            window_class.lpszClassName = name
            window_class.lpfnWndProc = self._window
            win32gui.RegisterClass(window_class)
            registered = True
            # A hidden top-level window receives power broadcasts; message-only
            # windows are excluded from broadcasts. Never call ShowWindow.
            self.hwnd = win32gui.CreateWindowEx(win32con.WS_EX_TOOLWINDOW | 0x08000000,
                name,'TailD collector lifecycle',win32con.WS_POPUP,0,0,0,0,0,0,instance,None)
            callback_type = ctypes.WINFUNCTYPE(None,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int)
            self.callback = callback_type(lambda context,row,kind:self._notify('interface'))
            self.api = ctypes.WinDLL('iphlpapi',use_last_error=True)
            self.api.NotifyIpInterfaceChange.argtypes = [wintypes.USHORT,callback_type,
                ctypes.c_void_p,wintypes.BOOLEAN,ctypes.POINTER(wintypes.HANDLE)]
            self.api.NotifyIpInterfaceChange.restype = wintypes.DWORD
            self.api.CancelMibChangeNotify2.argtypes = [wintypes.HANDLE]
            self.api.CancelMibChangeNotify2.restype = wintypes.DWORD
            code = self.api.NotifyIpInterfaceChange(0,self.callback,None,False,ctypes.byref(self.registration))
            if code:
                self.error = int(code)
            self.ready.set()
            win32gui.PumpMessages()
        except Exception as error:
            self.error = type(error).__name__
        finally:
            self.ready.set()
            if self.hwnd is not None and win32gui.IsWindow(self.hwnd):
                win32gui.DestroyWindow(self.hwnd)
            if registered:
                win32gui.UnregisterClass(name,instance)

    def start(self):
        if os.name != 'nt' or self.thread is not None:
            raise RuntimeError('Windows lifecycle unavailable')
        self.thread = threading.Thread(target=self._run,name='TailD Windows lifecycle')
        self.thread.start()
        self.ready.wait()

    def close(self):
        if self.stopped:
            return
        # Microsoft requires deregistration outside the callback and without a
        # resource its callback needs. Hold no collector/status lock here.
        if self.registration.value:
            code = self.api.CancelMibChangeNotify2(self.registration)
            if code:
                self.error = int(code)
                raise RuntimeError('Windows notification deregistration failed')
            self.registration = wintypes.HANDLE()
        if self.hwnd is not None and win32gui.IsWindow(self.hwnd):
            win32gui.PostMessage(self.hwnd,win32con.WM_CLOSE,0,0)
        if self.thread is not None:
            self.thread.join()
        self.stopped = True
