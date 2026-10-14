import test from 'node:test';
import assert from 'node:assert/strict';
import {DEFAULT_TIME_RANGE,presetBounds,utcTickPattern} from '../src/time-range.ts';

test('default is a rolling seven days, including across a local DST transition',()=>{
  assert.equal(DEFAULT_TIME_RANGE,'week');
  const now=new Date('2026-10-26T10:23:45.678Z');
  assert.deepEqual(presetBounds(DEFAULT_TIME_RANGE,now),{start:'2026-10-19T10:23:45.678Z',end:now.toISOString()});
});
test('shorter presets and local Today retain their existing meaning',()=>{
  const now=new Date('2026-10-14T13:00:00Z');
  for(const [preset,ms] of [['recent',900000],['hour',3600000]]){
    const result=presetBounds(preset,now);assert.equal(Date.parse(result.end)-Date.parse(result.start),ms);
  }
  assert.equal(presetBounds('today',now).start,new Date(now.getFullYear(),now.getMonth(),now.getDate()).toISOString());
});
test('multi-day chart ticks identify UTC dates rather than repeated clock times',()=>{
  assert.equal(utcTickPattern('2026-10-07T13:00:00Z','2026-10-14T13:00:00Z'),'%b %d');
  assert.equal(utcTickPattern('2026-10-14T12:45:00Z','2026-10-14T13:00:00Z'),'%H:%M');
});
