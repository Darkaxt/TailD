// SPDX-License-Identifier: GPL-3.0-only
// Adapted structured sections / expansion from Portmaster conn-details and accordion.
import {Component,Input} from '@angular/core';
import {CommonModule} from '@angular/common';
@Component({selector:'taild-evidence',standalone:true,imports:[CommonModule],
  template:`<section class="evidence-grid"><div *ngFor="let group of groups">
    <h3>{{group.name}}</h3><dl><ng-container *ngFor="let entry of group.entries">
      <dt>{{entry.label}}</dt><dd>{{entry.value}}</dd></ng-container></dl></div></section>
    <section *ngIf="candidates.length" class="candidate-evidence"><h3>Temporal DNS candidates · {{candidates.length}} events, not proven attribution</h3>
      <div class="table-scroll"><table><thead><tr><th>Question</th><th>Endpoint</th><th>Age (μs)</th><th>Source decision</th></tr></thead><tbody>
        <tr *ngFor="let candidate of candidatePage()"><td>{{candidate.question}}</td><td>{{candidate.endpoint}}</td><td>{{candidate.age_microseconds}}</td>
          <td><details><summary>Inspect candidate</summary><dl><dt>Decision ID</dt><dd>{{candidate.decision_id}}</dd><dt>Context capture</dt><dd>{{candidate.context_id}}</dd>
            <dt>TTL / cache validity</dt><dd>{{candidate.ttl_validity||'Unknown'}}</dd><dt>Reason</dt><dd>{{candidate.reason||'Unavailable'}}</dd><dt>Raw action</dt><dd>{{candidate.action||'Unavailable'}}</dd></dl></details></td></tr>
      </tbody></table></div><div class="pagination" *ngIf="candidates.length>20"><button (click)="candidateOffset=candidateOffset-20" [disabled]="candidateOffset===0">‹ Previous candidates</button>
        <span>{{candidateOffset+1}}–{{Math.min(candidateOffset+20,candidates.length)}} of {{candidates.length}}</span>
        <button (click)="candidateOffset=candidateOffset+20" [disabled]="candidateOffset+20>=candidates.length">Next candidates ›</button></div>
      <p class="hint">Candidates are not byte allocations. The entire bucket is counted once. Original evidence and JSON export retain every candidate.</p></section>
    <details><summary>Original structured evidence</summary><pre>{{original}}</pre></details>`,
  styles:[`:host{display:block;padding:16px 0}.evidence-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:24px}h3{font-size:12px;font-weight:500;color:var(--text-secondary);margin:0 0 12px}dl{margin:0;display:grid;grid-template-columns:minmax(100px,.7fr) minmax(0,1fr);gap:8px;font-size:12px}dt{color:var(--text-tertiary)}dd{margin:0;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:400px;overflow:auto;font-size:11px}`]})
export class Evidence {
  candidates:Record<string,any>[]=[];candidateOffset=0;Math=Math;
  candidatePage(){return this.candidates.slice(this.candidateOffset,this.candidateOffset+20)}
  original='';groups:{name:string;entries:{label:string;value:string}[]}[]=[];
  @Input() set data(data:Record<string,unknown>|null){
    if(!data){this.groups=[];return}
    this.original=JSON.stringify(data,null,2);
    this.candidates=Array.isArray(data['candidates'])?data['candidates']:[];this.candidateOffset=0;
    const groups=new Map<string,{label:string;value:string}[]>();
    const label=(key:string)=>key.replace(/_/g,' ');
    const visit=(value:unknown,key:string,group:string,depth:number)=>{
      if(value!==null&&typeof value==='object'&&depth<3){
        const entries=Object.entries(value);
        if(!entries.length)visit('None observed',key,group,4);
        else for(const [child,v] of entries.slice(0,100))visit(v,depth?key+' / '+child:child,depth?group:label(key),depth+1);
        if(entries.length>100)visit('Additional fields in original evidence',key,group,4);
      }else{
        if(!groups.has(group))groups.set(group,[]);
        groups.get(group)!.push({label:label(key),value:value===null?'Unavailable / unknown':typeof value==='object'?JSON.stringify(value):String(value)});
      }
    };
    for(const [key,value] of Object.entries(data))if(key!=='candidates')visit(value,key,'Observed fact',0);
    this.groups=[...groups].map(([name,entries])=>({name,entries}));
  }
}
