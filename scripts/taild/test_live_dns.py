import io
import json
import unittest
import asyncio
import threading
from unittest.mock import patch
import live_dns


class LiveTest(unittest.TestCase):
    def test_sse_comments_multiline_and_normalization(self):
        event={'timestamp':'2026-10-15T10:00:01.123Z','endpointId':'device',
               'question':'example.invalid','action':1,'rrType':'A',
               'answers':[{'ips':['192.0.2.1'],'geoip':{'countryCode':'DE','asn':123}}]}
        stream=io.BytesIO(b': heartbeat\n\n'+b'data: '+json.dumps(event).encode()+b'\n\n')
        values=list(live_dns.events(stream))
        raw=live_dns.normalize(values[0],'device')
        self.assertEqual(raw['action'],'1');self.assertEqual(raw['answers'],'192.0.2.1')
        self.assertEqual(raw['answerCountryCode'],'DE');self.assertEqual(raw['answerASN'],'123')
        event['timestamp']='2026-10-15T06:00:01.123-04:00'
        self.assertEqual(live_dns.normalize(event,'device')['timestamp'],'2026-10-15T10:00:01.123000Z')
        event['timestamp']='2026-10-15T10:00:01.123'
        with self.assertRaises(live_dns.LiveError):live_dns.normalize(event,'device')
        with self.assertRaises(live_dns.LiveError):live_dns.normalize(event,'other')

    def test_invalid_oversized_and_unterminated_events_are_not_facts(self):
        for raw in (b'data: not-json\n\n',b'data: '+b'x'*1048577+b'\n\n',b'data: {}'):
            with self.assertRaises(live_dns.LiveError):list(live_dns.events(io.BytesIO(raw)))

    def test_malformed_external_containers_are_source_errors(self):
        for raw in (b'[]',b'null',b'{"success":true,"body":[]}'):
            with self.assertRaises(live_dns.LiveError):live_dns.auth_token(raw)
        for answers in (None,1,{},'invalid'):
            with self.assertRaises(live_dns.LiveError):live_dns.normalize({
                'endpointId':'device','question':'example.invalid','timestamp':'2026-10-15T10:00:00Z','answers':answers},'device')

    def test_cancel_interrupts_original_connect_task_and_prestart(self):
        for before in (False,True):
            stream=live_dns.Stream();entered=threading.Event();exited=threading.Event()
            async def connecting(*args):
                entered.set()
                try:await asyncio.Future()
                finally:exited.set()
            with patch.object(stream,'_collect',side_effect=connecting):
                if before:stream.cancel()
                worker=threading.Thread(target=stream.run,args=('synthetic',{},lambda r:None,lambda:None))
                worker.start()
                if not before:entered.wait();stream.cancel()
                worker.join()
            self.assertFalse(worker.is_alive());self.assertIsNone(stream.task)
            if not before:self.assertTrue(exited.is_set())


if __name__=='__main__':unittest.main()
