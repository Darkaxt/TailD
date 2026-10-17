import test from 'node:test';
import assert from 'node:assert/strict';
import {mergeProgress} from '../src/progressive-batch.ts';

const event=(index,revision=7)=>({index,revision,aggregation_version:'metrics',correlation_version:'candidates',result:{revision,data:{index}}});
test('partial panels share one revision and preserve planned result slots',()=>{
  const indices=[0,1,2,3,7];
  const first=mergeProgress(null,event(1),indices);
  assert.equal(first.results[0],undefined);
  assert.deepEqual(first.results[1],event(1).result);
  const second=mergeProgress(first,event(4),indices);
  assert.equal(first.results[7],undefined,'Previous presentation is immutable');
  assert.deepEqual(second.results[7],event(4).result);
  assert.throws(()=>mergeProgress(second,event(0,8),indices),/revision/);
  assert.throws(()=>mergeProgress(second,event(5),indices),/index/);
});

test('bridge retains original promise until final response, then ignores late progress',async()=>{
  let listener,sent;
  globalThis.window={chrome:{webview:{addEventListener:(_,fn)=>listener=fn,postMessage:value=>sent=value}}};
  const {command}=await import('../src/bridge.ts');
  const progress=[];let finished=false;
  const result=command('view-query',{},value=>progress.push(value)).then(value=>{finished=true;return value});
  listener({data:{id:sent.id,ok:true,progress:true,data:{revision:7}}});
  await Promise.resolve();assert.equal(finished,false);assert.equal(progress.length,1);
  listener({data:{id:sent.id,ok:true,data:{results:[]}}});
  assert.deepEqual(await result,{results:[]});
  listener({data:{id:sent.id,ok:true,progress:true,data:{revision:8}}});
  assert.equal(progress.length,1);
});

test('compact terminal receipt completes acknowledged panels in original order',async()=>{
  let listener,sent;
  globalThis.window={chrome:{webview:{addEventListener:(_,fn)=>listener=fn,postMessage:value=>sent=value}}};
  const {command}=await import('../src/bridge.ts?streamed');
  const result=command('view-query',{queries:[{},{}]});
  for(const index of [1,0])listener({data:{id:sent.id,ok:true,progress:true,data:event(index)}});
  listener({data:{id:sent.id,ok:true,data:{revision:7,aggregation_version:'metrics',correlation_version:'candidates',streamed_results:2}}});
  assert.deepEqual((await result).results,[event(0).result,event(1).result]);
  const incomplete=command('view-query',{queries:[{},{}]});
  listener({data:{id:sent.id,ok:true,progress:true,data:event(0)}});
  listener({data:{id:sent.id,ok:true,data:{revision:7,aggregation_version:'metrics',correlation_version:'candidates',streamed_results:2}}});
  await assert.rejects(incomplete,/Incomplete/);
  const mismatched=command('view-query',{queries:[{}]});
  listener({data:{id:sent.id,ok:true,progress:true,data:event(0)}});
  listener({data:{id:sent.id,ok:true,data:{revision:8,aggregation_version:'metrics',correlation_version:'candidates',streamed_results:1}}});
  await assert.rejects(mismatched,/inconsistent/);
});
