"""Typed desktop control contracts; never operate the installed VPN."""
import copy
import json
import unittest
import threading
from unittest.mock import patch
from types import SimpleNamespace
try:
    import connectivity
except ImportError:
    connectivity=None


class DaemonFixture:
    def __init__(self):
        self.profile={'ID':'profile-a','Name':'Test account'}
        self.prefs={'CorpDNS':True,'ShieldsUp':False,'RouteAll':True,'ForceDaemon':True,
            'WantRunning':True,'ExitNodeID':'','ExitNodeAllowLANAccess':False,
            'AutoUpdate':{'Check':True,'Apply':False},'LocalDNSOverride':True,'AdvertiseRoutes':['10.9.0.0/16'],
            'Persist':{'PrivateNodeKey':'secret-not-for-renderer'},'Hostname':'unchanged'}
        self.resolver={'ProfileID':'profile-a','Configured':True,'Endpoint':'https://dns.example.invalid/test',
            'Applied':True,'Reason':'applied','CaptivePortal':False}
        self.policy={'Settings':{}}
        self.status={'BackendState':'Running','Version':'1.105.0-taild.10',
            'Self':{'ID':'self','HostName':'Test device','TailscaleIPs':['100.64.0.1']},
            'User':{'1':{'DisplayName':'Test user','LoginName':'test@example.invalid'}},
            'Peer':{'x':{'ID':'exit-a','HostName':'Test exit','DNSName':'exit.example.invalid.',
                'TailscaleIPs':['100.64.0.2'],'Online':True,'ExitNodeOption':True}}}
        self.writes=[];self.ignore_write=False;self.fail_write=False
    def __call__(self,method,path,body=None):
        if method=='GET':
            return copy.deepcopy({'status':self.status,'prefs':self.prefs,'profiles/current':self.profile,
                'local-dns':self.resolver,'policy/':self.policy,'version':{'long':'1.105.0-taild.10'}}[path])
        self.writes.append((method,path,copy.deepcopy(body)))
        if self.fail_write:raise connectivity.ConnectivityError('connectivity-unavailable')
        if not self.ignore_write:
            if path=='prefs':
                for field,value in body.items():
                    if not field.endswith('Set'):self.prefs[field]=copy.deepcopy(value)
            elif path=='local-dns':
                assert body['ProfileID']==self.profile['ID']
                self.resolver.update(Configured=body['Enabled'],Endpoint=body.get('Endpoint',''),Applied=body['Enabled'])
        return {}


class ConnectivityTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(connectivity,'Typed Tailscale desktop controls are missing')
        self.daemon=DaemonFixture();self.control=connectivity.Connectivity(None,call=self.daemon)
    def edit(self,preference,value,**extra):
        return self.control.dispatch('connectivity-edit',{'revision':self.control.read()['revision'],
            'preference':preference,'value':value,**extra})
    def test_read_is_whitelisted_and_never_mutates(self):
        data=self.control.read();self.assertEqual(self.daemon.writes,[])
        self.assertEqual(data['profile'],'profile-a')
        self.assertNotIn('PrivateNodeKey',json.dumps(data));self.assertNotIn('Persist',json.dumps(data))
        self.assertEqual(len(data['preferences']),5)
    def test_operational_resolver_state_does_not_invalidate_preferences(self):
        revision=self.control.read()['revision']
        self.daemon.resolver.update(Applied=False,Reason='temporary portal',CaptivePortal=True)
        result=self.control.dispatch('connectivity-edit',{'revision':revision,'preference':'unattended','value':False})
        self.assertFalse(next(p['value'] for p in result['preferences'] if p['id']=='unattended'))
    def test_incomplete_or_mixed_profile_resolver_is_not_disabled(self):
        for resolver in ({},{**self.daemon.resolver,'ProfileID':'another-profile'}):
            self.daemon.resolver=resolver
            with self.assertRaises(connectivity.ConnectivityError):self.control.read()
    def test_independent_gets_are_started_together(self):
        self.assertTrue(hasattr(self.control,'_read_all'),'Independent GET launch path is missing')
        barrier=threading.Barrier(5)
        def call(method,path,body=None):
            barrier.wait();return self.daemon(method,path,body)
        self.control.call=call
        self.assertEqual(self.control.read()['profile'],'profile-a')
    def test_each_tray_preference_uses_its_exact_mask_and_readback(self):
        for action,field,value,stored in [('allow-incoming','ShieldsUp',False,True),
            ('use-dns','CorpDNS',False,False),('use-subnets','RouteAll',False,False),
            ('unattended','ForceDaemon',False,False),('auto-update','AutoUpdate',True,{'Check':True,'Apply':True})]:
            result=self.edit(action,value)
            patch=self.daemon.writes[-1][2]
            self.assertEqual(patch[field],stored)
            self.assertEqual(patch[field+'Set'],{'CheckSet':True,'ApplySet':True} if field=='AutoUpdate' else True)
            self.assertEqual(len(patch),2)
            self.assertEqual(next(p for p in result['preferences'] if p['id']==action)['value'],value)
            self.assertEqual(self.daemon.prefs['Hostname'],'unchanged')
    def test_reset_is_confirmed_and_one_masked_operation(self):
        revision=self.control.read()['revision']
        with self.assertRaises(connectivity.ConnectivityError):self.control.dispatch('connectivity-reset',{'revision':revision})
        self.control.dispatch('connectivity-reset',{'revision':revision,'confirm':True})
        self.assertEqual(len(self.daemon.writes),1)
        self.assertTrue(self.daemon.prefs['CorpDNS']);self.assertFalse(self.daemon.prefs['LocalDNSOverride'])
        self.assertEqual(self.daemon.prefs['AutoUpdate'],{'Check':True,'Apply':False})
        self.assertEqual(self.daemon.prefs['Hostname'],'unchanged')
    def test_changed_profile_or_pref_rejects_before_mutation(self):
        for change in ('profile','prefs'):
            self.daemon.profile['ID']='profile-a'
            revision=self.control.read()['revision']
            if change=='profile':self.daemon.profile['ID']='profile-b'
            else:self.daemon.prefs['ShieldsUp']=not self.daemon.prefs['ShieldsUp']
            with self.assertRaisesRegex(connectivity.ConnectivityError,'connectivity-conflict'):
                self.control.dispatch('connectivity-edit',{'revision':revision,'preference':'use-dns','value':False})
        self.assertFalse(self.daemon.writes)
    def test_policy_locked_hidden_and_reset_cannot_bypass_restrictions(self):
        self.daemon.policy['Settings']={'EnableTailscaleDNS':{'Value':'always'}}
        self.assertFalse(next(p for p in self.control.read()['preferences'] if p['id']=='use-dns')['editable'])
        with self.assertRaisesRegex(connectivity.ConnectivityError,'connectivity-denied'):self.edit('use-dns',False)
        with self.assertRaisesRegex(connectivity.ConnectivityError,'connectivity-denied'):
            self.control.dispatch('connectivity-reset',{'revision':self.control.read()['revision'],'confirm':True})
        self.assertFalse(self.daemon.writes)
    def test_resolver_is_profile_pinned_validated_and_read_back(self):
        for endpoint in ('http://dns.example.invalid/test','https://user:pass@dns.example.invalid/test','https://127.0.0.1/test','https://dns.example.invalid/test?token=x'):
            with self.assertRaises(connectivity.ConnectivityError):self.edit('resolver',endpoint)
        data=self.edit('resolver','https://dns.example.invalid/new')
        self.assertEqual(self.daemon.writes[-1][2]['ProfileID'],'profile-a')
        self.assertEqual(data['resolver']['Endpoint'],'https://dns.example.invalid/new')
        self.edit('resolver-enabled',False);self.assertFalse(self.control.read()['resolver']['Configured'])
    def test_unknown_action_type_and_extra_arguments_never_reach_daemon(self):
        for pref,value in [('arbitrary-shell','x'),('use-dns',1),('exit-node','not-known')]:
            with self.assertRaises(connectivity.ConnectivityError):self.edit(pref,value)
        with self.assertRaises(connectivity.ConnectivityError):self.edit('use-dns',False,command='evil')
        self.assertFalse(self.daemon.writes)
    def test_exit_choice_lan_and_disconnect_are_explicit(self):
        self.edit('exit-node','exit-a');self.assertEqual(self.daemon.prefs['ExitNodeID'],'exit-a')
        self.edit('exit-node-lan',True);self.assertTrue(self.daemon.prefs['ExitNodeAllowLANAccess'])
        with self.assertRaises(connectivity.ConnectivityError):self.edit('connected',False)
        self.edit('connected',False,confirm=True);self.assertFalse(self.daemon.prefs['WantRunning'])
    def test_unconfirmed_readback_never_reports_success_or_retries(self):
        self.daemon.ignore_write=True
        with self.assertRaisesRegex(connectivity.ConnectivityError,'connectivity-outcome-unknown'):self.edit('use-dns',False)
        self.assertEqual(len(self.daemon.writes),1)
    def test_ambiguous_failure_is_not_retried(self):
        self.daemon.fail_write=True
        with self.assertRaisesRegex(connectivity.ConnectivityError,'connectivity-outcome-unknown'):self.edit('use-dns',False)
        self.assertEqual(len(self.daemon.writes),1)
    def test_about_is_read_only_and_contains_no_provider_credentials(self):
        data=self.control.dispatch('connectivity-about',{})
        self.assertEqual(data['product'],'TailD');self.assertEqual(data['version'],'1.105.0+10')
        self.assertEqual(self.daemon.writes,[])
    def test_incompatible_daemon_shapes_are_sanitized(self):
        self.daemon.policy['Settings']=None
        with self.assertRaisesRegex(connectivity.ConnectivityError,'connectivity-unavailable'):self.control.read()
        self.assertFalse(self.daemon.writes)
    def test_transport_uses_fixed_cli_windowless_stdin_and_no_shell(self):
        with patch('connectivity.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=b'{}')) as run:
            client=connectivity.Connectivity('synthetic-cli.exe')
            client._call('PATCH','prefs',{'CorpDNS':False,'CorpDNSSet':True})
            args,kwargs=run.call_args
            self.assertEqual(args[0][1:],['debug','localapi','PATCH','/localapi/v0/prefs','-'])
            self.assertNotIn('shell',kwargs);self.assertNotIn('timeout',kwargs)
            self.assertEqual(json.loads(kwargs['input']),{'CorpDNS':False,'CorpDNSSet':True})
    def test_exit_lan_policy_and_advertisement_preserve_existing_subnet_routes(self):
        self.daemon.policy['Settings']={'ExitNodeAllowLANAccess':{'Value':'never'}}
        with self.assertRaisesRegex(connectivity.ConnectivityError,'connectivity-denied'):self.edit('exit-node-lan',True)
        self.daemon.policy['Settings']={}
        self.edit('run-exit-node',True)
        self.assertEqual(set(self.daemon.prefs['AdvertiseRoutes']),{'10.9.0.0/16','0.0.0.0/0','::/0'})
        self.edit('run-exit-node',False)
        self.assertEqual(self.daemon.prefs['AdvertiseRoutes'],['10.9.0.0/16'])


if __name__=='__main__':unittest.main()
