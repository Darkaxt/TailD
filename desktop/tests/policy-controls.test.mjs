import test from 'node:test';
import assert from 'node:assert/strict';
import {filterChoices,filterAction,optionEnabled} from '../src/policy-controls.ts';
test('one native filter has one explicit checked state',()=>{
  assert.deepEqual(filterChoices({PK:'ads',name:'Ads',status:1}),[{id:'ads',label:'Ads',enabled:true}]);
  assert.equal(filterChoices({PK:'ads',status:0})[0].enabled,false);
});
test('native levels are deduplicated and show the one active provider level',()=>{
  const choices=filterChoices({PK:'ads',name:'Ads',status:1,action:{lvl:'strict'},
    levels:[{name:'ads',title:'Standard'},{name:'strict',title:'Strict'}]});
  assert.deepEqual(choices,[{id:'ads',label:'Standard',enabled:false},{id:'strict',label:'Strict',enabled:true}]);
});
test('unknown status or unsupported active level never looks disabled',()=>{
  assert.equal(filterChoices({PK:'ads'})[0].enabled,null);
  assert.equal(filterChoices({PK:'ads',status:1,action:{lvl:'unreturned'}})[0].enabled,null);
  assert.equal(optionEnabled({configured:false,value:null}),null);
  assert.equal(optionEnabled({value:'0'}),false);
  assert.equal(optionEnabled({value:1}),true);
});
test('single-value settings offer only the opposite-state action',()=>{
  assert.equal(filterAction({PK:'ads',status:1}).label,'Disable');
  assert.equal(filterAction({PK:'ads',status:0}).label,'Enable');
  assert.equal(filterAction({PK:'ads'}).disabled,true);
});
test('multi-value selection is separate from current provider state',()=>{
  const filter={PK:'ads',status:1,action:{lvl:'strict'},levels:[{name:'strict',title:'Strict'}],selected:'ads'};
  assert.deepEqual(filterAction(filter),{id:'ads',status:1,label:'Apply level',disabled:false});
  assert.equal(filterChoices(filter).find(c=>c.id==='strict').enabled,true);
  assert.equal(filterAction({...filter,selected:'strict'}).label,'Disable');
  assert.equal(filterAction({...filter,status:0}).label,'Enable');
});
