"""Control D SSE observations: bounded frames, cancellable socket, no replay loop."""
import asyncio
from datetime import datetime,timezone
import json
import threading
from urllib.parse import urlencode
import controld

LIMIT=1024*1024


class LiveError(ValueError):pass


def events(response):
    data=[];size=0
    while True:
        line=response.readline(LIMIT+1)
        if not line:
            if data:raise LiveError('incomplete-event')
            return
        size+=len(line)
        if size>LIMIT:raise LiveError('resource-limit')
        if line in (b'\n',b'\r\n'):
            if data:
                try:value=json.loads(b'\n'.join(data))
                except (ValueError,UnicodeError):raise LiveError('invalid-event') from None
                if not isinstance(value,dict):raise LiveError('invalid-event')
                yield value
            data=[];size=0
        elif line.startswith(b'data:'):
            data.append(line[5:].lstrip(b' ').rstrip(b'\r\n'))


def normalize(event, endpoint):
    if (not isinstance(event,dict) or event.get('endpointId')!=endpoint or
            not isinstance(event.get('question'),str) or len(event['question'])>4096):
        raise LiveError('invalid-event')
    try:
        # Unlike CSV, live SSE uses explicit non-UTC offsets. Never interpret a
        # naive provider timestamp in the laptop's local timezone.
        value=event['timestamp']
        if not isinstance(value,str) or 'T' not in value:raise ValueError()
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        if parsed.tzinfo is None:raise ValueError()
        timestamp=parsed.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
    except (KeyError,ValueError,TypeError,OverflowError):raise LiveError('invalid-event') from None
    raw={k:str(event[k]) for k in ('endpointId','question','rrType','profileId','clientId',
        'sourceIp','protocol','statusCode','trigger','triggerValue','action')
         if k in event and isinstance(event[k],(str,int)) and not isinstance(event[k],bool)}
    raw['timestamp']=timestamp
    addresses=[];geos=[]
    answers=event.get('answers',[])
    if not isinstance(answers,list):raise LiveError('invalid-event')
    for answer in answers:
        if not isinstance(answer,dict) or not isinstance(answer.get('ips'),list):
            raise LiveError('invalid-event')
        if not all(isinstance(ip,str) for ip in answer['ips']):raise LiveError('invalid-event')
        addresses.extend(answer['ips']);geos.append(answer.get('geoip',{}))
    raw['answers']=';'.join(addresses)
    categories=event.get('categories')
    if isinstance(categories,list):
        raw['categories']=[{k:str(item[k])[:256] for k in ('categoryId','categoryName')
                           if isinstance(item.get(k),(str,int))} for item in categories[:64] if isinstance(item,dict)]
    for field,key in (('answerCountryCode','countryCode'),('answerASN','asn'),
                      ('answerISP','isp'),('answerCity','city')):
        values={str(geo[key]) for geo in geos if isinstance(geo,dict) and geo.get(key) is not None}
        if len(values)==1 and len(geos)==sum(isinstance(g,dict) and g.get(key) is not None for g in geos):
            raw[field]=values.pop()
    return raw


class Stream:
    def __init__(self):
        self.stopped=threading.Event();self.lock=threading.Lock();self.loop=None;self.task=None

    def cancel(self):
        self.stopped.set()
        with self.lock:
            if self.loop is not None:self.loop.call_soon_threadsafe(self.task.cancel)

    async def _collect(self,token,provider,on_event,on_connected):
        import aiohttp
        host=controld._instance(provider['instance'])+'.analytics.controld.com'
        endpoint=controld._identifier(provider['endpoint']);organization=provider.get('organization')
        headers={'Authorization':'Bearer '+controld._header(token),'User-Agent':'TailD-live-dns'}
        if organization is not None:headers['X-Force-Org-Id']=controld._header(organization)
        def accepted(response):
            if response.status!=200:
                raise controld.ControlDError('Control D live read rejected',status=response.status,
                                             state=controld._error_state(response.status))
        try:
            # Async cancellation owns DNS/TCP/TLS/header/body phases, not merely
            # an already-established socket. No application timeout/retry loop.
            async with aiohttp.ClientSession(headers=headers,cookie_jar=aiohttp.DummyCookieJar(),
                    timeout=aiohttp.ClientTimeout(total=None,connect=None,sock_connect=None,sock_read=None),
                    read_bufsize=LIMIT,trust_env=False) as client:
                async with client.get('https://'+host+'/v2/auth/token',allow_redirects=False) as response:
                    accepted(response);raw=bytearray()
                    async for chunk in response.content.iter_chunked(8192):
                        raw.extend(chunk)
                        if len(raw)>LIMIT:raise LiveError('resource-limit')
                    auth=auth_token(raw)
                path='/v2/activity-log/realtime?'+urlencode({'endpointId':endpoint,'authToken':auth})
                async with client.get('https://'+host+path,allow_redirects=False) as response:
                    auth=path=None;accepted(response)
                    if response.headers.get('Content-Type','').split(';')[0].strip()!='text/event-stream':
                        raise LiveError('invalid-content-type')
                    on_connected();data=[];size=0
                    async for line in response.content:
                        size+=len(line)
                        if size>LIMIT:raise LiveError('resource-limit')
                        if line in (b'\n',b'\r\n'):
                            if data:
                                try:event=json.loads(b'\n'.join(data))
                                except (ValueError,UnicodeError):raise LiveError('invalid-event') from None
                                on_event(normalize(event,endpoint))
                            data=[];size=0
                        elif line.startswith(b'data:'):data.append(line[5:].lstrip(b' ').rstrip(b'\r\n'))
                    if data:raise LiveError('incomplete-event')
        except (aiohttp.ClientError,OSError,ValueError) as error:
            if isinstance(error,LiveError):raise
            raise LiveError('disconnected') from None

    def run(self,token,provider,on_event,on_connected):
        loop=asyncio.new_event_loop()
        try:
            with self.lock:
                self.loop=loop;self.task=loop.create_task(self._collect(token,provider,on_event,on_connected))
                if self.stopped.is_set():self.task.cancel()
            try:loop.run_until_complete(self.task)
            except asyncio.CancelledError:
                if not self.stopped.is_set():raise LiveError('disconnected') from None
        finally:
            with self.lock:
                self.loop=self.task=None
            loop.run_until_complete(loop.shutdown_asyncgens());loop.close()


def auth_token(raw):
    try:
        envelope=json.loads(raw)
        if not isinstance(envelope,dict) or envelope.get('success') is not True:raise ValueError()
        body=envelope.get('body')
        if not isinstance(body,dict) or not isinstance(body.get('token'),str) or not body['token']:raise ValueError()
        return body['token']
    except (ValueError,TypeError):raise LiveError('invalid-auth-response') from None
