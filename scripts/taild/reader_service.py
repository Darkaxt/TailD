"""SCM lifecycle adapter for the existing fixed-schema, owner-only reader."""
import json
from pathlib import Path
import sys
import threading

import reader
import packaged
import servicemanager
import win32service
import win32serviceutil
import win32security
import win32api
import win32event

NAME='TailDReadOnlyReader'


class Service(win32serviceutil.ServiceFramework):
    _svc_name_=NAME
    _svc_display_name_='TailD read-only GlassWire reader'
    def __init__(self,args):
        super().__init__(args);self.server=None;self.stop_requested=False;self.lifecycle=threading.Lock()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        with self.lifecycle:
            self.stop_requested=True
            if self.server is not None:self.server.stop()

    def SvcRun(self):
        # ServiceFramework reports RUNNING before SvcDoRun by default. This
        # service instead reports readiness only after its authenticated pipe
        # actually exists; failed startup returns the framework's STOPPED error.
        self.SvcDoRun()
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)

    def SvcDoRun(self):
        try:
            home=Path(sys.executable).resolve().parent
            config=json.loads((home/'installation.json').read_text(encoding='utf-8'))
            sid=config['owner_sid'];win32security.ConvertStringSidToSid(sid)
            reader.drop_unused_privileges()
            ready=win32event.CreateEvent(None,True,False,None)
            errors=[]
            with self.lifecycle:
                self.server=reader.PipeServer(packaged.reader_instance(sid),sid,reader.GlassWireSource(owner_sid=sid),ready_handle=ready)
                if self.stop_requested:self.server.stop()
            def serve():
                try:self.server.serve()
                except BaseException as error:errors.append(error)
                finally:win32event.SetEvent(ready)
            worker=threading.Thread(target=serve,name='TailD read-only pipe')
            worker.start()
            try:
                win32event.WaitForSingleObject(ready,win32event.INFINITE)
                if self.server.ready.is_set() and not errors and not self.stop_requested:
                    self.ReportServiceStatus(win32service.SERVICE_RUNNING)
                worker.join()
                if errors:raise errors[0]
            finally:win32api.CloseHandle(ready)
        except Exception:
            servicemanager.LogErrorMsg('TailD read-only reader could not start; configuration or source boundary unavailable.')
            raise
        finally:
            with self.lifecycle:
                if self.server is not None:self.server.close()


def main():
    servicemanager.Initialize();servicemanager.PrepareToHostSingle(Service)
    servicemanager.StartServiceCtrlDispatcher()
