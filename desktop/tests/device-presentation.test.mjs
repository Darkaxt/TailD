import {test} from 'node:test';
import assert from 'node:assert/strict';
import {relativeSeen,osSymbol} from '../src/device-presentation.ts';
test('relative last seen retains honest missing, online and clock states',()=>{
  const now=Date.parse('2026-10-17T12:00:00Z');
  for(const [age,label] of [[86400,'24h ago'],[3*86400,'3 days ago'],[31*86400,'1 month ago'],[364*86400,'12 months ago'],[365*86400,'1 year ago']])
    assert.equal(relativeSeen(new Date(now-age*1000).toISOString(),false,now),label);
  assert.equal(relativeSeen(null,true,now),'Online now');
  assert.equal(relativeSeen(null,false,now),'Not reported');
  assert.equal(relativeSeen('bad',null,now),'Not reported');
  assert.equal(relativeSeen(new Date(now+1000).toISOString(),false,now),'Clock ahead');
  for(const os of ['windows','android','linux','macOS','iOS',null])assert.ok(osSymbol(os).path&&osSymbol(os).name);
});
