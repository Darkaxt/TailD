"""Actual Windows diagnostic-file boundary, without bypassing owner elevation checks."""
import json
import os
from pathlib import Path
import unittest
import uuid

import runtime
import history


@unittest.skipUnless(os.name=='nt','Windows rename sharing contract')
class StatusPublicationTest(unittest.TestCase):
    def test_diagnostic_sharing_failure_is_separate_and_recovers_on_next_publication(self):
        import win32api,win32con,win32file
        root=Path(os.environ['TAILD_PACKAGE_TEST_OUTPUT'])/uuid.uuid4().hex
        root.parent.mkdir(parents=True,exist_ok=True)
        root=history.private_directory(root)
        # Do not start an elevated collector on the hosted administrator runner.
        # This tests the real publication boundary; owning-user source lifecycle
        # is independently verified by test_runtime and the live product workflow.
        collector=runtime.Collector(root,None,instance='publication-'+uuid.uuid4().hex)
        collector._publish_status()
        target=root/'runtime-status.json'
        held=win32file.CreateFile(str(target),win32con.GENERIC_READ,
            win32con.FILE_SHARE_READ|win32con.FILE_SHARE_WRITE,None,win32con.OPEN_EXISTING,0,None)
        try:
            collector._publish_status()
            self.assertFalse(collector.write_error)
            self.assertEqual(collector._state()['diagnostics']['state'],'unavailable')
            self.assertIn(collector.diagnostics['winerror'],(5,32))
        finally:win32api.CloseHandle(held)
        collector._publish_status()
        self.assertEqual(collector.diagnostics['state'],'available')
        self.assertFalse(collector.write_error)
        self.assertEqual(json.loads(target.read_bytes())['state'],'disabled')


if __name__=='__main__':unittest.main()
