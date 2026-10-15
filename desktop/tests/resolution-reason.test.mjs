import test from 'node:test';
import assert from 'node:assert/strict';
import {resolutionReason,resolutionCategories} from '../src/resolution-reason.ts';

test('uses provider trigger and list label, not a classification as blocking cause',()=>{
  const row={outcome:'block',reason:'filter',reason_value:'ads',fact:{raw:{categories:[{categoryName:'Technology'}]}}};
  assert.equal(resolutionReason(row,[{PK:'ads',name:'Ads & Trackers'}],[]),'Filter / list · Ads & Trackers (ads)');
  assert.deepEqual(resolutionCategories(row),['Technology']);
  assert.equal(resolutionReason({outcome:'block',fact:row.fact},[],[]),'Blocking reason unavailable');
});
test('keeps custom rules, services, unrecognized triggers and missing names explicit',()=>{
  assert.equal(resolutionReason({reason:'custom',reason_value:'example.invalid'},[],[]),'Custom rule · example.invalid');
  assert.equal(resolutionReason({reason:'service',reason_value:'test'},[],[{PK:'test',name:'Test service'}]),'Service · Test service (test)');
  assert.equal(resolutionReason({reason:'filter'},[],[]),'Filter / list · name not supplied');
  assert.equal(resolutionReason({reason:'new-provider-code',reason_value:'literal'},[],[]),'new-provider-code · literal');
  assert.deepEqual(resolutionCategories({fact:{raw:{categories:'[{"categoryName":"Business"}]'}}}),['Business']);
  assert.deepEqual(resolutionCategories({}),[]);
});
