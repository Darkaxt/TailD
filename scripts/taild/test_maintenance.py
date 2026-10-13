"""Actual Windows event-driven owner collector update shutdown contract."""
import os
import threading
import unittest
import uuid

import maintenance
import reader


@unittest.skipUnless(os.name=='nt','Windows maintenance events')
class MaintenanceTest(unittest.TestCase):
    def test_stop_event_closes_only_the_named_instance_without_changing_settings(self):
        class Collector:
            condition=threading.Condition()
            closing=False
            config={'traffic':True,'dns':False}
        collector=Collector();other=Collector()
        first=maintenance.StopEvent(collector,reader.current_sid(),'test-'+uuid.uuid4().hex)
        second=maintenance.StopEvent(other,reader.current_sid(),'test-'+uuid.uuid4().hex)
        try:
            maintenance.signal(reader.current_sid(),first.instance)
            first.thread.join()
            self.assertTrue(collector.closing)
            self.assertFalse(other.closing)
            self.assertEqual(collector.config,{'traffic':True,'dns':False})
        finally:first.close();second.close()

    def test_invalid_instance_and_sid_are_not_event_names(self):
        for sid,instance in (('owner','collector'),(reader.current_sid(),'../other')):
            with self.assertRaises(ValueError):maintenance.name(sid,instance)


if __name__=='__main__':unittest.main()
