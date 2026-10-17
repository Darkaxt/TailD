// SPDX-License-Identifier: GPL-3.0-only
import {mergeProgress} from './progressive-batch.ts';
import type {ProgressiveBatch,BatchProgress} from './progressive-batch.ts';
interface WebView {postMessage(value:unknown):void;addEventListener(type:string,fn:(event:MessageEvent)=>void):void}
const webview=(window as unknown as {chrome?:{webview:WebView}}).chrome?.webview;
let sequence=0;
const pending=new Map<number,{lane:string;resolve:(value:unknown)=>void;reject:(error:Error)=>void;progress?:(value:unknown)=>void;count?:number;batch?:ProgressiveBatch}>();
const errors:Record<string,string>={
  'history-corrupt':'Local history could not be read: SQLite reported a malformed database. History is preserved; collection status is shown separately. Diagnose the history before attempting recovery.',
  'history-busy':'Local history is busy. Wait for the active operation, then refresh the view.',
  'history-read-failed':'Local history could not be read. History is preserved; check Sources & health and refresh explicitly.',
  'connectivity-unavailable':'The local Tailscale service is unavailable or incompatible. Reload to check its current state.',
  'connectivity-denied':'This setting is controlled by system policy or the active account. No change was made.',
  'connectivity-conflict':'The active profile or settings changed. Reload before making another change.',
  'connectivity-confirm-required':'Confirm this disruptive network action first.',
  'connectivity-invalid-resolver':'Use an HTTPS DNS hostname and path, without credentials, query parameters or fragments.',
  'connectivity-outcome-unknown':'The change could not be confirmed. Reload to inspect current settings; nothing was retried.',
  'management-conflict':'The profile or its affected devices changed. Reload and preview the change again.',
  'management-invalid-change':'That change is invalid or targets an unavailable resource.',
  'management-denied':'Control D denied access. Check permissions and profile lock state.',
  'management-rate-limited':'Control D is rate limiting requests. No policy change was retried.',
  'management-write-rejected':'Control D rejected the change. Reload to inspect current policy.',
  'management-outcome-unknown':'The outcome could not be verified. Reload policy before trying another explicit change.',
  'management-account-mismatch':'The READ and Write credentials do not belong to the same selected account.',
  'management-read-credential-required':'Configure the owning-user READ credential first.',
  'management-write-credential-required':'A separate Write credential is required for management actions. READ collection is unchanged.',
  'management-resource-unavailable':'Control D policy is unavailable or incompatible. No automatic mutation was attempted.',
  'invalid-export-destination':'Choose a new file in a local, non-linked folder. Existing files are never overwritten.',
  'stale-revision':'History changed. Refresh explicitly to open a new consistent revision.',
  'invalid-query':'That filter or query is not supported for this fact mode.',
  'resource-limit':'Narrow the requested interval or scope; this operation exceeded its resource bound.',
  'stopping':'Collector stopped.',
  'invalid-settings':'Check the binding and cadence fields. Previous settings are unchanged.',
  'explicit-provider-required':'Complete a Control D endpoint binding before enabling DNS activity.',
  'credential-not-accepted':'The READ token was not accepted. Enter a valid READ credential.',
  'read-only-confirmation-required':'Confirm that the token has READ permissions only.',
  'backpressure':'The collector command queue is full. Wait for the current operation.',
  'write-error':'History writes have stopped. Restore disk capacity, then explicitly resume collection.'};
webview?.addEventListener('message',event=>{
  const message=event.data,request=pending.get(message?.id);
  if(!request)return;
  if(message.ok===true&&message.progress===true){
    try{
      if(request.count!==undefined){
        if(request.batch?.results[message.data?.index])throw new Error('Duplicate query panel');
        request.batch=mergeProgress(request.batch||null,message.data as BatchProgress,Array.from({length:request.count},(_,i)=>i));
      }
      request.progress?.(message.data)
    }catch(error){pending.delete(message.id);request.reject(error instanceof Error?error:new Error('Invalid query progress'))}
    return;
  }
  pending.delete(message.id);
  if(message.ok===true){
    const terminal=message.data;
    if(terminal?.streamed_results!==undefined){
      const batch=request.batch;
      if(!batch||terminal.streamed_results!==request.count||batch.results.filter(Boolean).length!==request.count||
        batch.revision!==terminal.revision||batch.aggregation_version!==terminal.aggregation_version||batch.correlation_version!==terminal.correlation_version){
        request.reject(new Error('Incomplete or inconsistent analytics reply. Refresh explicitly.'));return;
      }
      request.resolve(batch);
    }else request.resolve(terminal);
  }
  else request.reject(new Error(errors[message.state]||'Collector unavailable. Reopen TailD to reconnect.'));
});
export function command<T=unknown>(op:string,body:unknown={},progress?:(value:unknown)=>void):Promise<T>{
  if(!webview)return Promise.reject(new Error('Open TailD using its desktop launcher.'));
  const lane=['connectivity-read','connectivity-edit','connectivity-reset','connectivity-about','activity-read','activity-configure','activity-delete','analytics-state','analytics-configure'].includes(op)?'device':
    ['management-read','management-prepare','management-apply','management-cancel'].includes(op)?'policy':op==='recent-dns'?'recent':'analytics';
  if([...pending.values()].filter(request=>request.lane===lane).length>=(lane==='analytics'?4:2))return Promise.reject(new Error('An operation is already pending.'));
  const id=++sequence;
  return new Promise<T>((resolve,reject)=>{
    const queries=op==='view-query'&&body&&typeof body==='object'?(body as {queries?:unknown}).queries:undefined;
    const count=Array.isArray(queries)&&queries.length>=1&&queries.length<=16?queries.length:undefined;
    pending.set(id,{lane,resolve:value=>resolve(value as T),reject,progress,count});webview.postMessage({id,op,body});
  });
}
