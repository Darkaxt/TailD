import test from 'node:test';
import assert from 'node:assert/strict';
import {describeIngestion} from '../src/ingestion-state.ts';

const state={state:'collecting',settings:{traffic:true,dns:true},sources:{
  traffic:{state:'collecting',progress:{phase:'reading',start:'2026-10-12T00:00:00Z',end:'2026-10-12T01:00:00Z',committed_reads:12}},
  dns:{state:'starting'}}};
const catalog={intervals:{traffic:{start:'2026-10-12T00:00:00Z',end:'2026-10-12T00:35:00Z',latest_observation:'2026-10-12T00:34:59Z'},
  dns:{start:null,end:null},snapshots:{start:'2026-10-14T00:00:00Z',end:'2026-10-14T12:00:00Z'}}};

test('older imported facts explain empty recent graphs without fake completion',()=>{
  const view=describeIngestion(state,catalog,'2026-10-14T10:00:00Z','2026-10-14T11:00:00Z');
  assert.equal(view.active,true);
  assert.match(view.title,/Reading history/);
  assert.equal(view.sources[0].aheadOfStoredData,true);
  assert.match(view.sources[0].activity,/12 source reads committed/);
  assert.match(view.sources[0].activity,/2026-10-12T00:00:00Z/);
  assert.equal(view.sources[0].latest,'2026-10-12T00:34:59Z');
  assert.equal(view.sources[1].latest,null);
  assert.doesNotMatch(JSON.stringify(view),/percent|ETA|12:00:00Z/);
});
test('paused and provider failures are not labelled as active imports',()=>{
  const paused=describeIngestion({...state,state:'paused'},catalog,'2026-10-12T00:01:00Z','2026-10-12T00:02:00Z');
  assert.equal(paused.active,false);assert.match(paused.title,/paused/i);
  assert.equal(paused.sources[0].aheadOfStoredData,false);
  const failed=describeIngestion({...state,state:'stale',sources:{traffic:{state:'write-error'},dns:{state:'rate-limited'}}},catalog,'2026-10-14T10:00:00Z','2026-10-14T11:00:00Z');
  assert.equal(failed.active,false);assert.match(failed.sources[0].activity,/write-error/);
  assert.match(failed.sources[1].activity,/rate-limited/);
});
test('last observation is not asserted to be complete coverage or a progressing read',()=>{
  const done=describeIngestion({...state,sources:{traffic:{state:'collecting',last_success_utc:'2026-10-14T11:00:00Z'},dns:{state:'disabled'}}},catalog,'2026-10-12T00:01:00Z','2026-10-12T00:02:00Z');
  assert.equal(done.active,false);assert.equal(done.sources.length,2);
  assert.match(done.sources[0].activity,/Last read/);
  assert.doesNotMatch(done.sources[0].activity,/complete|100%/i);
});
