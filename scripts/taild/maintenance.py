"""Fixed owner/instance-bound update stop event; no general elevated RPC."""
import re
import threading


def name(sid,instance):
    if not isinstance(sid,str) or not re.fullmatch(r'S-1-[0-9-]+',sid) or not isinstance(instance,str) or not re.fullmatch('[A-Za-z0-9-]{1,96}',instance):
        raise ValueError('invalid-maintenance-identity')
    return 'Global\\Darkaxt.TailD.UpdateStop.'+sid+'.'+instance


class StopEvent:
    def __init__(self,collector,sid,instance):
        import pywintypes,win32event,win32security
        self.instance=instance;self.collector=collector
        attributes=pywintypes.SECURITY_ATTRIBUTES()
        # Only the owner and trusted installation identities can request a
        # graceful stop. Other users do not gain access to the owner data pipe.
        attributes.SECURITY_DESCRIPTOR=win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
            'D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;'+sid+')',win32security.SDDL_REVISION_1)
        self.event=win32event.CreateEvent(attributes,True,False,name(sid,instance))
        self.done=win32event.CreateEvent(None,True,False,None)
        self.thread=threading.Thread(target=self._wait,name='TailD update stop')
        self.thread.start()

    def _wait(self):
        import win32event
        if win32event.WaitForMultipleObjects([self.event,self.done],False,win32event.INFINITE)==win32event.WAIT_OBJECT_0:
            with self.collector.condition:
                self.collector.closing=True
                self.collector.condition.notify()

    def close(self):
        import win32api,win32event
        win32event.SetEvent(self.done);self.thread.join()
        win32api.CloseHandle(self.event);win32api.CloseHandle(self.done)


def signal(sid,instance):
    import pywintypes,win32api,win32con,win32event
    try:handle=win32event.OpenEvent(win32con.EVENT_MODIFY_STATE,False,name(sid,instance))
    except pywintypes.error as error:
        if error.winerror==2:return False
        raise
    try:win32event.SetEvent(handle)
    finally:win32api.CloseHandle(handle)
    return True
