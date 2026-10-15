import test from 'node:test';
import assert from 'node:assert/strict';

test('local commands retain capacity while analytics is pending, without abandoning it',async()=>{
  let listener;const sent=[];
  globalThis.window={chrome:{webview:{addEventListener:(_,fn)=>listener=fn,postMessage:value=>sent.push(value)}}};
  const {command}=await import('../src/bridge.ts');
  const queries=Array.from({length:4},()=>command('view-query'));
  const local=command('connectivity-read');
  const about=command('connectivity-about');
  await assert.rejects(command('connectivity-read'),/pending/);
  await assert.rejects(command('state'),/pending/);
  const outcome=local.then(()=>({ok:true}),error=>({ok:false,message:error.message}));
  await Promise.resolve();
  const request=sent.find(r=>r.op==='connectivity-read');
  if(request)listener({data:{id:request.id,ok:true,data:{profile:'synthetic'}}});
  const aboutRequest=sent.find(r=>r.op==='connectivity-about');
  if(aboutRequest)listener({data:{id:aboutRequest.id,ok:true,data:{version:'synthetic'}}});
  for(const request of sent.filter(r=>r.op==='view-query'))listener({data:{id:request.id,ok:true,data:{results:[]}}});
  assert.deepEqual(await outcome,{ok:true});await about;await Promise.all(queries);
});
