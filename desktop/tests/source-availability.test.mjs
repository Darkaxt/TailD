import test from 'node:test';
import assert from 'node:assert/strict';
import {availableSources} from '../src/source-availability.ts';

test('missing integrations hide irrelevant analytics but retain recorded domains',()=>{
  const runtime={settings:{provider:null},integration_ready:{dns:false,traffic:false}};
  assert.deepEqual(availableSources(runtime,{sources:[]}),{traffic:false,dns:false});
  assert.deepEqual(availableSources(runtime,{sources:[{kind:'traffic'}]}),{traffic:true,dns:false});
  assert.deepEqual(availableSources(runtime,{sources:[{kind:'dns'}]}),{traffic:false,dns:true});
});
test('integration readiness is independent from recording consent and transient outages',()=>{
  assert.deepEqual(availableSources({analytics_enabled:false,integration_ready:{dns:true,traffic:true}},null),{traffic:true,dns:true});
  assert.deepEqual(availableSources({sources:{traffic:{state:'source-unavailable'}},integration_ready:{traffic:false,dns:false}},
    {sources:[{kind:'traffic'},{kind:'dns'}]}),{traffic:true,dns:true});
});
