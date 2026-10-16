"""Opt-in, read-only Tailscale observations. Never persist raw daemon messages.

Presence is control-plane presence, not reachability. Missing observations are
unknown; a transfer disappearing is not evidence of success or local file save.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
import http.client
import io
import json
import ntpath
import re
import threading
import uuid

import history
import reader

OPERATIONS=('activity-read','activity-configure','activity-delete')
PIPE=r'\\.\pipe\ProtectedPrefix\Administrators\Tailscale\tailscaled'
# Current core supports InitialStatus/PeerChanges, not obsolete InitialNetMap.
WATCH_MASK=(1<<1)|(1<<2)|(1<<4)|(1<<6)|(1<<7)|(1<<12)|(1<<14)
WATCH='/localapi/v0/watch-ipn-bus?mask='+str(WATCH_MASK)
PATHS=('/localapi/v0/status','/localapi/v0/profiles/current','/localapi/v0/local-dns',WATCH)
MAX_MESSAGE=2*1024*1024


def retention_floor(store,now):
    days,floor=store.db.execute('SELECT retention_days,expiry_floor FROM settings').fetchone()
    return max(floor,history.instant(now)-days*86400*1000000)


def text(value,maximum=256):
    return value if isinstance(value,str) and len(value)<=maximum and not any(ord(c)<32 or 0xD800<=ord(c)<=0xDFFF for c in value) else None


def boolean(value):return value if type(value) is bool else None


def size(value):return value if type(value) is int and -1<=value<2**63 else None


def started_at(value):
    """Go time.Time may use a local offset and RFC3339 nanoseconds, not UTC."""
    if not isinstance(value,str):return None
    match=re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(\d{1,9}))?(?:Z|[+-]\d{2}:\d{2})',value)
    if not match:return None
    try:dt=datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)
    except (ValueError,OverflowError):return None
    fraction=(match[1] or '').ljust(9,'0')
    return dt.date().isoformat()+'T'+dt.strftime('%H:%M:%S')+'.'+fraction+'Z'


class Tracker:
    """Only called by the existing single SQLite writer; no additional store."""
    def __init__(self,store):
        self.store=store;self.session=uuid.uuid4().hex;self.baselines=set();self.profile=None

    def _get(self,key):
        row=self.store.db.execute('SELECT data FROM snapshots WHERE id=?',(key,)).fetchone()
        return json.loads(row[0]) if row else None

    def _put(self,kind,profile,key,data,at,origin=None):
        time=history.instant(at);origin=history.instant(origin or at)
        floor=retention_floor(self.store,at)
        if origin<floor or self.store._suppressed('activity',profile,origin):return
        old=self._get(key)
        if old==data:return
        revision=self.store._bump()
        self.store.db.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET '
            'time=excluded.time,end=excluded.end,data=excluded.data,revision=excluded.revision',
            (key,kind,profile,time,time+1,history.packed(data),revision))

    def _expire(self,at):
        # Frequent transfer notifications must not scan GlassWire facts or run
        # application orphan maintenance. The normal store owns other sources.
        floor=retention_floor(self.store,at)
        self.store.db.execute("DELETE FROM snapshots WHERE kind>='activity-' AND kind<'activity.' AND end<=?",(floor,))
        self.store.db.execute("DELETE FROM suppressions WHERE kind='activity' AND end<=?",(floor,))

    def _event(self,profile,kind,value,at):
        self._put('activity-event',profile,uuid.uuid4().hex,
            {'type':kind,'value':value,'observed_at':at},at)

    def snapshot(self,profile,status,resolver,at,*,health=None):
        if not text(profile) or not isinstance(status,dict) or not isinstance(resolver,dict):return
        with self.store.transaction():
            self._expire(at)
            if self.profile is not None and profile!=self.profile:self._gap(self.profile,'profile-changed',at)
            self.profile=profile
            baseline=profile not in self.baselines
            if baseline and self.store.db.execute("SELECT 1 FROM snapshots WHERE scope=? AND kind='activity-device' LIMIT 1",(profile,)).fetchone():
                self._gap(profile,'new-observation-session',at)
            self.baselines.add(profile)
            self._state(profile,'connection',{'state':text(status.get('BackendState')) or 'Unknown'},at,baseline)
            exit_node=status.get('ExitNodeStatus') or {}
            if not isinstance(exit_node,dict):exit_node={}
            self._state(profile,'exit-node',{'id':text(exit_node.get('ID'))},at,baseline)
            resolver_state={key:boolean(resolver.get(field)) for key,field in
                (('configured','Configured'),('applied','Applied'),('captive_portal','CaptivePortal'))}
            previous=self._get(history.digest(['activity-state',profile,'resolver'])) or {}
            warnings=health.get('Warnings') if isinstance(health,dict) else None
            resolver_state['fallback']=('local-dns-encrypted-recovery' in warnings if isinstance(warnings,dict)
                else False if isinstance(health,dict) and 'Warnings' in health and warnings is None
                else previous.get('fallback'))
            self._state(profile,'resolver',resolver_state,at,baseline)
            peers=status.get('Peer')
            if not isinstance(peers,dict):return  # Missing is not an empty peer list.
            current=set()
            for raw in peers.values():
                if not isinstance(raw,dict) or not text(raw.get('ID')):continue
                key=history.digest(['activity-device',profile,raw['ID']]);current.add(key)
                old=self._get(key)
                state='online' if raw.get('Online') is True else 'offline' if raw.get('Online') is False else 'unknown'
                item={'id':raw['ID'],'name':text(raw.get('HostName')) or text(raw.get('DNSName')) or raw['ID'],
                    'os':text(raw.get('OS')),'presence':state,'observed_at':at}
                if baseline or old is None or old['presence']=='unknown' and state!='unknown':
                    self._event(profile,'peer-baseline',{k:item[k] for k in ('id','name','os','presence')},at)
                if not baseline and old and old['presence']!='unknown' and old['presence']!=state:
                    self._event(profile,'peer-presence',{'id':item['id'],'name':item['name'],
                        'os':item['os'],'from':old['presence'],'to':state},at)
                self._put('activity-device',profile,key,item,at)
            for key,data in self.store.db.execute('SELECT id,data FROM snapshots WHERE kind=? AND scope=?',
                    ('activity-device',profile)).fetchall():
                if key not in current:
                    old=json.loads(data)
                    if old['presence']!='unknown':
                        self._event(profile,'peer-unavailable',{'id':old['id'],'name':old['name'],
                            'reason':'not in current visible peer set; presence unknown'},at)
                        old.update(presence='unknown',observed_at=at)
                        self._put('activity-device',profile,key,old,at)
            if baseline:self._event(profile,'baseline',{'coverage':'visible peers; observation began here'},at)

    def _state(self,profile,kind,value,at,baseline):
        key=history.digest(['activity-state',profile,kind]);old=self._get(key)
        baseline=baseline or old is None
        if baseline or old!=value:
            self._event(profile,kind,{'current':value,'previous':None if baseline else old,'baseline':baseline},at)
        # State marker shares retention/deletion with activity history; excluded
        # from event queries (kind differs). It contains only whitelisted fields.
        self._put('activity-state',profile,key,value,at)

    def _gap(self,profile,reason,at):
        self.baselines.discard(profile)
        self._event(profile,'observation-gap',{'reason':reason},at)
        for key,kind,data in self.store.db.execute('SELECT id,kind,data FROM snapshots WHERE scope=? AND '
                'kind IN (?,?)',(profile,'activity-device','activity-transfer')).fetchall():
            item=json.loads(data)
            if kind=='activity-device':item.update(presence='unknown',observed_at=at)
            elif item['result']=='in-progress':item.update(result='unknown',last_observed_at=at)
            else:continue
            self._put(kind,profile,key,item,at,item.get('started_at'))

    def gap(self,profile,reason,at):
        if not text(profile):return
        with self.store.transaction():self._gap(profile,reason,at)

    def notify(self,profile,raw,at):
        if not text(profile) or not isinstance(raw,dict):return
        with self.store.transaction():
            self._expire(at)
            for direction,field in (('sent','OutgoingFiles'),('received','IncomingFiles')):
                values=raw.get(field)
                if not isinstance(values,list):continue  # nil means no update.
                current=set();complete=len(values)<=4096
                for value in values[:4096]:
                    if not isinstance(value,dict):complete=False;continue
                    name=text(value.get('Name'),1024);started=started_at(value.get('Started'))
                    declared=size(value.get('DeclaredSize'));count=size(value.get('Sent' if direction=='sent' else 'Received'))
                    try:history.instant(started)
                    except history.HistoryError:complete=False;continue
                    if not name or declared is None or count is None or count<0:complete=False;continue
                    name=ntpath.basename(name.replace('/','\\'))
                    if not name:complete=False;continue
                    identity=text(value.get('ID')) if direction=='sent' else None
                    key=history.digest(['activity-transfer',profile,direction,identity or [name,started]])
                    current.add(key);old=self._get(key)
                    result=('sent' if value.get('Succeeded') is True else 'failed' if value.get('Succeeded') is False else 'unknown') \
                        if direction=='sent' and value.get('Finished') is True else \
                        'received-by-daemon' if direction=='received' and value.get('Done') is True else 'in-progress'
                    if old and old['result'] in ('sent','failed','received-by-daemon'):continue
                    item={'id':key,'direction':direction,'name':name,'peer_id':text(value.get('PeerID')),
                        'started_at':started,'declared_bytes':None if declared==-1 else declared,'observed_bytes':count,
                        'first_observed_at':old['first_observed_at'] if old else at,'last_observed_at':at,'result':result}
                    self._put('activity-transfer',profile,key,item,at,started)
                if not complete:continue  # Malformed / bounded input is not a complete disappearance report.
                for key,data in self.store.db.execute('SELECT id,data FROM snapshots WHERE kind=? AND scope=?',
                        ('activity-transfer',profile)).fetchall():
                    item=json.loads(data)
                    if item['direction']==direction and key not in current and item['result']=='in-progress':
                        item.update(result='unknown',last_observed_at=at)
                        self._put('activity-transfer',profile,key,item,at,item['started_at'])


def read(store,body,now):
    if not isinstance(body,dict) or set(body)-{'view','profile','start','end','search'}:raise ValueError('invalid-query')
    kind={'devices':'activity-device','events':'activity-event','transfers':'activity-transfer'}.get(body.get('view','events'))
    if not kind:raise ValueError('invalid-query')
    search=body.get('search','');profile=body.get('profile','')
    if text(search,128) is None or text(profile) is None:raise ValueError('invalid-query')
    end=history.instant(body.get('end',now));start=history.instant(body.get('start',history.utc(end-7*86400*1000000)))
    if start>=end:raise ValueError('invalid-query')
    floor=retention_floor(store,now)
    args=[kind,max(start,floor),end];where='kind=? AND time>=? AND time<=?'
    if profile:where+=' AND scope=?';args.append(profile)
    if search:where+=' AND instr(lower(data),lower(?))>0';args.append(search)
    rows=store.db.execute('SELECT scope,data FROM snapshots WHERE '+where+' ORDER BY time DESC,id LIMIT 201',args).fetchall()
    profiles=[row[0] for row in store.db.execute("SELECT DISTINCT scope FROM snapshots WHERE kind>='activity-' AND kind<'activity.' AND end>? ORDER BY scope",(floor,))]
    return {'rows':[dict(json.loads(data),profile=scope) for scope,data in rows[:200]],'truncated':len(rows)>200,
        'profiles':profiles,'start':history.utc(start),'end':history.utc(end),'coverage':'observations-only'}


def delete(store,body,now):
    if set(body)!={'confirm'} or body['confirm'] is not True:raise ValueError('invalid-query')
    with store.transaction():
        end=history.instant(now)+1
        store.db.execute("DELETE FROM snapshots WHERE kind LIKE 'activity-%'")
        store.db.execute('INSERT INTO suppressions VALUES(?,?,?,?,?)',('activity',None,0,end,None))
        store._bump()
    return {'deleted':True,'replay_suppression':True}


class PipeIO(io.RawIOBase):
    def __init__(self,handle,stop):self.handle=handle;self.stop=stop;super().__init__()
    def readable(self):return True
    def readinto(self,buffer):
        import win32file,pywintypes
        try:
            value,count=reader._overlapped(self.handle,self.stop,
                lambda ov:win32file.ReadFile(self.handle,len(buffer),ov))
            buffer[:count]=value[1][:count];return count
        except pywintypes.error as error:
            if error.winerror in (109,232):return 0
            raise


class Stream:
    """One owner thread, fixed GETs, cancellable IO with settled completion."""
    def __init__(self):
        import win32event
        self.stopped=threading.Event();self.lock=threading.Lock()
        self.stop=win32event.CreateEvent(None,True,False,None)
        self.profile=None;self.health=None

    def cancel(self):
        import win32event
        with self.lock:
            self.stopped.set()
            if self.stop is not None:win32event.SetEvent(self.stop)

    @contextmanager
    def request(self,path):
        import win32file,win32con
        if path not in PATHS:raise reader.ReaderError('invalid-command')
        if self.stopped.is_set():raise reader.ReaderError('stopped')
        handle=win32file.CreateFile(PIPE,win32con.GENERIC_READ|win32con.GENERIC_WRITE,0,None,
            win32con.OPEN_EXISTING,win32con.FILE_FLAG_OVERLAPPED|0x100000|0x10000,None)
        incoming=None;response=None
        try:
            raw=('GET '+path+' HTTP/1.1\r\nHost: local-tailscaled.sock\r\nConnection: close\r\n\r\n').encode('ascii')
            _,count=reader._overlapped(handle,self.stop,lambda ov:win32file.WriteFile(handle,raw,ov))
            if count!=len(raw):raise reader.ReaderError('unavailable')
            incoming=io.BufferedReader(PipeIO(handle,self.stop))
            class Socket:
                def makefile(self,*args):return incoming
            response=http.client.HTTPResponse(Socket());response.begin()
            if response.status!=200:raise reader.ReaderError('unavailable')
            yield response
        finally:
            if response is not None:response.close()
            if incoming is not None:incoming.close()
            handle.Close()

    def get(self,path):
        with self.request('/localapi/v0/'+path) as response:
            raw=response.read(MAX_MESSAGE+1)
            if len(raw)>MAX_MESSAGE:raise reader.ReaderError('resource-limit')
            value=reader.decode_message(raw,maximum=MAX_MESSAGE)
            if not isinstance(value,dict):raise reader.ReaderError('unavailable')
            return value

    def snapshot(self,receive):
        first=self.get('profiles/current');status=self.get('status');resolver=self.get('local-dns');last=self.get('profiles/current')
        if first.get('ID')!=last.get('ID') or resolver.get('ProfileID')!=last.get('ID'):
            raise reader.ReaderError('connectivity-conflict')
        profile=text(last.get('ID')) or 'signed-out'
        if profile!=self.profile:self.health=None
        self.profile=profile
        receive('snapshot',profile,(status,resolver,self.health))

    def run(self,receive,connected):
        import pywintypes
        try:
            self.snapshot(receive)
            with self.request(WATCH) as response:
                connected()
                while not self.stopped.is_set():
                    line=response.readline(MAX_MESSAGE+1)
                    if not line:break
                    if len(line)>MAX_MESSAGE:raise reader.ReaderError('resource-limit')
                    raw=reader.decode_message(line,maximum=MAX_MESSAGE)
                    if not isinstance(raw,dict):raise reader.ReaderError('unavailable')
                    if isinstance(raw.get('Health'),dict):self.health=raw['Health']
                    if any(key in raw for key in ('InitialStatus','State','Prefs','Health','SelfChange','PeersChanged','PeersRemoved')):
                        self.snapshot(receive)
                    receive('notify',self.profile,raw)
        except (pywintypes.error,http.client.HTTPException) as error:
            raise reader.ReaderError('stopped' if self.stopped.is_set() else 'unavailable') from None
        finally:
            with self.lock:
                if self.stop is not None:self.stop.Close();self.stop=None
