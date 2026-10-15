import contextlib
import http.client
import importlib
import io
import json
import threading
import unittest


class CredentialEntryTest(unittest.TestCase):
    def test_loopback_capability_origin_and_successful_single_registration(self):
        module=importlib.import_module('credential_entry')
        class Vault:
            def __init__(self,value=None): self.value=value
            def read(self): return self.value
            def replace(self,token): self.value=token
        read=Vault('existing-read-token')
        write=Vault()
        verified=[]
        server=module.create_server(write,read,lambda token:verified.append(token))
        self.assertEqual(server.server_address[0],'127.0.0.1')
        def request(method,path,body=None,headers=None):
            worker=threading.Thread(target=server.handle_request)
            worker.start()
            connection=http.client.HTTPConnection(*server.server_address)
            try:
                connection.request(method,path,body,headers or {})
                response=connection.getresponse()
                result=(response.status,response.read(),response.getheader('Content-Security-Policy'))
            finally:
                connection.close()
                worker.join()
            return result
        output=io.StringIO()
        try:
            with contextlib.redirect_stderr(output),contextlib.redirect_stdout(output):
                self.assertEqual(request('GET','/wrong')[0],404)
                self.assertEqual(request('GET',server.entry_path,
                    headers={'Host':'untrusted.invalid'})[0],404)
                status,page,csp=request('GET',server.entry_path)
                self.assertEqual(status,200)
                self.assertIn(b'type="password"',page)
                self.assertIn("frame-ancestors 'none'",csp)
                payload=json.dumps({'token':'synthetic-write-token'})
                headers={'Content-Type':'application/json','Origin':'https://untrusted.invalid',
                         'X-TailD-Entry':server.entry_id}
                self.assertEqual(request('POST',server.entry_path,payload,headers)[0],403)
                self.assertIsNone(write.read())
                headers['Origin']=server.origin
                headers['X-TailD-Entry']='wrong-capability'
                self.assertEqual(request('POST',server.entry_path,payload,headers)[0],403)
                self.assertIsNone(write.read())
                headers['X-TailD-Entry']=server.entry_id
                status,body,_=request('POST',server.entry_path,payload,headers)
                self.assertEqual(status,200)
                self.assertEqual(json.loads(body),{'stored':True})
                self.assertTrue(server.finished)
                self.assertIsNone(server.failure)
                self.assertEqual(write.read(),'synthetic-write-token')
                self.assertEqual(read.read(),'existing-read-token')
                self.assertEqual(verified,['synthetic-write-token'])
                self.assertNotIn(b'synthetic-write-token',body)
                self.assertEqual(request('POST',server.entry_path,payload,headers)[0],409)
        finally:
            server.server_close()
        self.assertNotIn('synthetic-write-token',output.getvalue())

    def test_provider_rejection_finishes_without_registering(self):
        module=importlib.import_module('credential_entry')
        class Vault:
            def read(self): return None
            def replace(self,token): self.fail('Unverified token stored')
        def reject(token): raise ValueError('must-not-echo-token')
        server=module.create_server(Vault(),Vault(),reject)
        worker=threading.Thread(target=server.handle_request)
        worker.start()
        connection=http.client.HTTPConnection(*server.server_address)
        try:
            connection.request('POST',server.entry_path,json.dumps({'token':'synthetic-write-token'}),
                {'Content-Type':'application/json','Origin':server.origin,'X-TailD-Entry':server.entry_id})
            response=connection.getresponse()
            self.assertEqual(response.status,400)
            self.assertNotIn(b'must-not-echo-token',response.read())
        finally:
            connection.close()
            worker.join()
            server.server_close()
        self.assertTrue(server.finished)
        self.assertEqual(server.failure,'Credential registration failed; no secret details are logged')
