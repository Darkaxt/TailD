// SPDX-License-Identifier: GPL-3.0-only
// Diagnostic presentation only: no source reads, inferred completion or timers.
interface Source {state:string;last_success_utc?:string;progress?:unknown;result?:unknown}
interface State {state:string;settings:{traffic:boolean;dns:boolean};sources:Record<string,Source>}
interface Interval {start:string|null;end:string|null;latest_observation?:string|null}
export interface IngestionCatalog {intervals:Record<string,Interval>}
export function describeIngestion(state:State|null,catalog:IngestionCatalog|null,start:string,end:string){
  const paused=state?.state==='paused';
  const sources=(['traffic','dns'] as const).filter(kind=>state?.settings[kind]).map(kind=>{
    const source=state!.sources[kind]||{state:'starting'};
    const progress=source.progress as {phase?:string;start?:string;end?:string;committed_reads?:number}|undefined;
    const interval=catalog?.intervals[kind];
    const active=!paused&&source.state==='collecting'&&!source.last_success_utc;
    let activity=paused?'Paused · no new reads':source.state==='starting'?'Waiting for source read':
      source.last_success_utc?'Last read '+source.last_success_utc:source.state;
    if(active){
      activity=progress?.phase==='discovering'?'Discovering retained history':'Reading history';
      if(progress?.start&&progress?.end)activity+=' · '+progress.start+' → '+progress.end;
      if(Number.isSafeInteger(progress?.committed_reads)&&progress!.committed_reads!>=0)
        activity+=' · '+progress!.committed_reads+' source reads committed';
    }
    const aheadOfStoredData=!!start&&(!interval?.end||Date.parse(interval.end)<=Date.parse(start));
    const outsideStoredData=aheadOfStoredData||!!(end&&interval?.start&&Date.parse(interval.start)>=Date.parse(end));
    return {kind,label:kind==='traffic'?'GlassWire traffic':'Control D DNS',active,activity,
      latest:interval?.latest_observation??null,aheadOfStoredData,outsideStoredData};
  });
  const active=sources.some(s=>s.active);
  return {active,title:paused?'History ingestion paused':active?'Reading history':
    state?.state==='disabled'?'Collection disabled':'History status',sources};
}
