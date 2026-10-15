"""Single-use owner-launched Write credential entry; no clipboard, files or startup."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import secrets

import credentials


def create_server(write_store, read_store, verify):
    original_read=read_store.read()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass  # Request URLs, bodies and credentials must not enter logs.

        def reply(self,status,body,content_type='application/json'):
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'none'; connect-src 'self'; "
                "style-src 'unsafe-inline'; script-src 'nonce-"+self.server.entry_id+
                "'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def allowed_path(self):
            return (self.path==self.server.entry_path and
                    self.headers.get('Host')==self.server.origin.removeprefix('http://'))

        def do_GET(self):
            if not self.allowed_path():
                self.reply(404,b'{}')
                return
            html='''<!doctype html><meta charset="utf-8"><title>TailD secure credential entry</title>
<style>body{font:16px system-ui;background:#211f1f;color:#f9f7f6;margin:4rem auto;max-width:38rem;padding:1rem}
input{display:block;width:95%;padding:.8rem;margin:1rem 0}button{padding:.7rem 1.2rem}</style>
<h1>TailD management credential</h1><p>One-time local Windows vault registration. No clipboard or files.</p>
<form><label for="token">Control D Write token</label>
<input id="token" type="password" autocomplete="off" spellcheck="false" required>
<button>Register securely</button></form><p id="status" role="status"></p>
<script nonce="NONCE">document.querySelector('form').addEventListener('submit',async e=>{
e.preventDefault();const input=document.querySelector('#token'),button=document.querySelector('button');
button.disabled=true;document.querySelector('#status').textContent='Verifying and registering…';
try{const response=await fetch(location.pathname,{method:'POST',headers:{'Content-Type':'application/json',
'X-TailD-Entry':'NONCE'},body:JSON.stringify({token:input.value})});input.value='';
const result=await response.json();document.querySelector('#status').textContent=
response.ok&&result.stored?'Stored in Windows Credential Manager. You may close this tab.':'Registration failed. No secret details logged.';
}catch{input.value='';document.querySelector('#status').textContent='Registration response unavailable. Check the local command result.';}
});</script>'''.replace('NONCE',self.server.entry_id)
            self.reply(200,html.encode('utf-8'),'text/html; charset=utf-8')

        def do_POST(self):
            if not self.allowed_path():
                self.reply(404,b'{}')
                return
            if (self.headers.get('Origin')!=self.server.origin or
                    not secrets.compare_digest(self.headers.get('X-TailD-Entry',''),self.server.entry_id)):
                self.reply(403,b'{}')
                return
            if self.server.finished:
                self.reply(409,b'{}')
                return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=4096 or self.headers.get('Content-Type')!='application/json':
                    raise ValueError('Invalid credential entry envelope')
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict) or set(body)!={'token'}:
                    raise ValueError('Invalid credential entry fields')
                token=credentials.validate(body['token'])
                if token==original_read:
                    raise ValueError('Write entry must be a distinct token')
                verify(token)
                write_store.replace(token)
                if write_store.read()!=token or read_store.read()!=original_read:
                    raise credentials.CredentialError('Credential continuity check failed')
                self.server.finished=True
                self.reply(200,b'{"stored":true}')
            except Exception:
                self.server.failure='Credential registration failed; no secret details are logged'
                self.server.finished=True
                self.reply(400,b'{"stored":false}')

    server=HTTPServer(('127.0.0.1',0),Handler)
    server.entry_id=secrets.token_urlsafe(32)
    server.entry_path='/entry/'+server.entry_id
    server.origin='http://127.0.0.1:'+str(server.server_port)
    server.finished=False
    server.failure=None
    return server


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-write-access',action='store_true',required=True)
    parser.parse_args(argv)
    read_store=credentials.CredentialStore()
    write_store=credentials.CredentialStore(credentials.WRITE_TARGET)
    original_read=read_store.read()
    if not original_read or write_store.read() is not None:
        raise credentials.CredentialError('Requires existing Read credential and an empty Write entry')
    import controld
    expected_account=controld._body('/users',original_read).get('PK')
    def verify(token):
        account=controld._body('/users',token)
        if expected_account is None or account.get('PK')!=expected_account:
            raise credentials.CredentialError('Credential belongs to a different account')
    with create_server(write_store,read_store,verify) as server:
        print(json.dumps({'entry_url':server.origin+server.entry_path,'single_use':True}),flush=True)
        while not server.finished:
            server.handle_request()
        if server.failure:
            print(json.dumps({'stored':False,'error':server.failure}),flush=True)
            return 1
        print(json.dumps({'stored':True,'read_preserved':True,'provider_authenticated':True,
                          'storage':'Windows Credential Manager','permission':'write'}),flush=True)
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print(json.dumps({'stored':False,'error':'Credential entry unavailable; no secret details logged'}))
        raise SystemExit(1) from None
