// One in-flight read snapshot; never combine panels from different revisions.
export interface ProgressiveResult {revision:number;[key:string]:any}
export interface ProgressiveBatch {revision:number;aggregation_version:string;correlation_version:string;results:ProgressiveResult[]}
export interface BatchProgress {revision:number;aggregation_version:string;correlation_version:string;index:number;result:ProgressiveResult}
export function mergeProgress(current:ProgressiveBatch|null,event:BatchProgress,indices:number[]):ProgressiveBatch {
  if(!Number.isInteger(event.index)||event.index<0||event.index>=indices.length)throw new Error('Invalid progress index');
  if(event.result.revision!==event.revision||current&&(current.revision!==event.revision||
    current.aggregation_version!==event.aggregation_version||current.correlation_version!==event.correlation_version))
    throw new Error('Inconsistent progress revision');
  const results=current?[...current.results]:[];
  results[indices[event.index]]=event.result;
  return {revision:event.revision,aggregation_version:event.aggregation_version,correlation_version:event.correlation_version,results};
}
