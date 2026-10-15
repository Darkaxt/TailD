// SPDX-License-Identifier: GPL-3.0-only
interface WebView {postMessage(value:unknown):void;addEventListener(type:string,fn:(event:MessageEvent)=>void):void}
const webview=(window as unknown as {chrome?:{webview:WebView}}).chrome?.webview;
let sequence=0;
const pending=new Map<number,{resolve:(value:unknown)=>void;reject:(error:Error)=>void;progress?:(value:unknown)=>void}>();
const errors:Record<string,string>={
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
    try{request.progress?.(message.data)}catch(error){pending.delete(message.id);request.reject(error instanceof Error?error:new Error('Invalid query progress'))}
    return;
  }
  pending.delete(message.id);
  if(message.ok===true)request.resolve(message.data);
  else request.reject(new Error(errors[message.state]||'Collector unavailable. Reopen TailD to reconnect.'));
});
export function command<T=unknown>(op:string,body:unknown={},progress?:(value:unknown)=>void):Promise<T>{
  if(!webview)return Promise.reject(new Error('Open TailD using its desktop launcher.'));
  if(pending.size>=4)return Promise.reject(new Error('An operation is already pending.'));
  const id=++sequence;
  return new Promise<T>((resolve,reject)=>{
    pending.set(id,{resolve:value=>resolve(value as T),reject,progress});webview.postMessage({id,op,body});
  });
}
