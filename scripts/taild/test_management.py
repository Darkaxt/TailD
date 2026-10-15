"""Incident-management contracts; no production policy mutation."""
import copy
import unittest
from unittest.mock import patch
import management


def snapshot():
    def resource(key, value): return {'state':'available','data':{key:value}}
    return {'endpoint':'device','profile':'profile','resources':{
        'endpoints':resource('devices',[{'PK':'device','name':'This device','profile':{'PK':'profile'}}]),
        'profiles':resource('profiles',[{'PK':'profile','name':'Shared'}]),
        'rules':resource('rules',[]),'filters':resource('filters',[
            {'PK':'ads','levels':[{'name':'ads_small'}],'status':1}]),
        'services':resource('services',[{'PK':'test','name':'Test','action':{'do':0,'status':1}}]),
        'options':resource('options',[{'PK':'block_rfc1918','value':1}])}}


class ManagementTest(unittest.TestCase):
    def setUp(self):
        self.current=snapshot();self.writes=[]
        self.manager=management.Management()
        self.addCleanup(patch.stopall)
        patch('management.credentials.CredentialStore.__init__',return_value=None).start()
        patch('management.credentials.CredentialStore.read',return_value='synthetic').start()
        patch('management.controld._body',side_effect=lambda path,*a:
            {'options':[{'PK':'block_rfc1918','type':'toggle','default_value':0}]} if path=='/profiles/options' else {'PK':'account'}).start()
        patch('management.controld.policy_snapshot',side_effect=lambda *a,**k:copy.deepcopy(self.current)).start()
        def apply(*args):
            self.writes.append(args)
            payload=args[3]
            if args[2].endswith('/rules'):
                self.current['resources']['rules']['data']['rules']=[{
                    'PK':payload['hostnames[]'][0],'comment':payload.get('comment',''),
                    'action':{'do':payload['do'],'status':payload['status']}}]
            return {}
        patch('management.write',side_effect=apply).start()
        self.provider={'account_scope':'local','endpoint':'device'}

    def call(self,op,body):return self.manager.dispatch(op,body,self.provider)

    def test_requires_preview_confirmation_and_one_use(self):
        change={'kind':'rule','hostname':'example.invalid','do':1,'status':1,'comment':'Incident'}
        preview=self.call('management-prepare',{'endpoint':'device','change':change})
        self.assertEqual(len(self.writes),0)
        with self.assertRaises(management.ManagementError):
            self.call('management-apply',{'ticket':preview['ticket'],'confirm':False})
        # Failed confirmation consumes nothing; an explicit valid confirmation writes once.
        result=self.call('management-apply',{'ticket':preview['ticket'],'confirm':True})
        self.assertEqual(result['state'],'applied')
        self.assertEqual(self.writes[0][1:3],('POST','/profiles/profile/rules'))
        with self.assertRaises(management.ManagementError):
            self.call('management-apply',{'ticket':preview['ticket'],'confirm':True})
        self.assertEqual(len(self.writes),1)

    def test_changed_shared_scope_or_policy_rejects_without_writing(self):
        preview=self.call('management-prepare',{'endpoint':'device','change':{
            'kind':'filter','id':'ads_small','status':0}})
        self.current['resources']['endpoints']['data']['devices'].append(
            {'PK':'second','profile':{'PK':'profile'}})
        with self.assertRaisesRegex(management.ManagementError,'management-conflict'):
            self.call('management-apply',{'ticket':preview['ticket'],'confirm':True})
        self.assertEqual(self.writes,[])

    def test_denies_arbitrary_routes_fields_and_unreturned_resources(self):
        for change in ({'kind':'filter','id':'../users','status':1},
                       {'kind':'option','id':'unreturned','status':1},
                       {'kind':'rule','hostname':'https://example.invalid','do':1,'status':1},
                       {'kind':'rule','hostname':'example.invalid','do':1,'status':1,'url':'https://other.invalid'}):
            with self.assertRaisesRegex(management.ManagementError,'management-invalid-change'):
                self.call('management-prepare',{'endpoint':'device','change':change})
        self.assertEqual(self.writes,[])

    def test_read_path_never_loads_write_credential(self):
        targets=[]
        with patch('management.credentials.CredentialStore') as vault:
            vault.side_effect=lambda *a: targets.append(a) or type('Vault',(),{'read':lambda s:'read'})()
            result=self.call('management-read',{'endpoint':'device'})
        self.assertEqual(targets,[()]);self.assertEqual(result['profile'],'profile')

    def test_account_mismatch_denies(self):
        with patch('management.controld._body',side_effect=[{'PK':'one'},{'PK':'two'}]):
            with self.assertRaisesRegex(management.ManagementError,'management-account-mismatch'):
                self.call('management-prepare',{'endpoint':'device','change':{
                    'kind':'filter','id':'ads','status':0}})
        self.assertEqual(self.writes,[])

    def test_successful_http_without_matching_readback_is_not_applied(self):
        preview=self.call('management-prepare',{'endpoint':'device','change':{
            'kind':'filter','id':'ads','status':0}})
        with self.assertRaisesRegex(management.ManagementError,'management-outcome-unknown'):
            self.call('management-apply',{'ticket':preview['ticket'],'confirm':True})

    def test_post_write_binding_change_and_readback_errors_are_uncertain(self):
        for failure in ('reassigned','catalog','vault','resource'):
            preview=self.call('management-prepare',{'endpoint':'device','change':{
                'kind':'rule','hostname':'example.invalid','do':1,'status':1,'comment':''}})
            original=self.manager._read
            calls=0
            def read(*args):
                nonlocal calls
                calls+=1
                value=original(*args)
                if calls==2:
                    if failure=='reassigned':value['profile']='other-profile'
                    elif failure=='catalog':raise management.ManagementError('management-resource-unavailable')
                    elif failure=='resource':value['resources']['rules']['state']='unavailable'
                    else:raise management.credentials.CredentialError('Unavailable vault')
                return value
            with patch.object(self.manager,'_read',side_effect=read):
                with self.assertRaisesRegex(management.ManagementError,'management-outcome-unknown'):
                    self.call('management-apply',{'ticket':preview['ticket'],'confirm':True})

    def test_rule_comment_is_part_of_readback(self):
        current=snapshot();current['resources']['rules']['data']['rules']=[{
            'PK':'example.invalid','comment':'OLD','action':{'do':1,'status':1}}]
        self.assertFalse(management.verified(current,{'kind':'rule','hostname':'example.invalid','do':1,'status':1,'comment':'NEW'}))


if __name__=='__main__':unittest.main()
