// SPDX-License-Identifier: GPL-3.0-only
import {Component,Input,OnInit,signal,computed} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {command} from './bridge';
import {bytes,exact} from './portmaster/charts';

type Row=Record<string,any>;
interface AppRead {revision:number;start:string;end:string;apps:Row[];selected:Row|null;destinations:Row[];estimated_domains:Row[];unmatched_bytes:string;estimate_method:string;
  source_status:Row;coverage:string;provider_bound:boolean}

@Component({selector:'taild-app-dns',standalone:true,imports:[CommonModule,FormsModule],template:`
 <section id="app-dns-workspace" [attr.aria-busy]="busy()">
  <div class="app-dns-toolbar">
   <button *ngIf="selectedPath()" class="icon-button" (click)="select(null)" aria-label="Back to applications" title="Back to applications"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 5-7 7 7 7M7 12h14" /></svg></button>
   <h2>{{selectedPath()?(data()?.selected?.name || 'App diagnosis'):'Applications'}}</h2>
   <span class="hint" *ngIf="data() as d" role="status">DNS · {{sourceLabel(d.source_status.state)}}</span>
   <label class="compact-choice">Period<select [(ngModel)]="days" (change)="load(true)" [disabled]="busy()"><option [ngValue]="1">Last 24 hours</option><option [ngValue]="7">Last 7 days</option></select></label>
   <button class="icon-button" (click)="load(true)" [disabled]="busy()" aria-label="Refresh app observations" title="Refresh"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5M20 12a8 8 0 1 0-2 6M20 7l-3-3" /></svg></button>
   <button *ngIf="selectedPath()" class="icon-button" (click)="export()" [disabled]="busy()||!data()" aria-label="Export this app snapshot" title="Export app snapshot"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m-5-5 5 5 5-5M4 15v6h16v-6" /></svg></button>
   <button class="icon-button" (click)="showCoverage=!showCoverage" [attr.aria-expanded]="showCoverage" aria-label="Coverage and source details" title="Coverage and source details"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10v1" /></svg></button>
  </div>
  <p class="error" *ngIf="error()" role="alert">{{error()}}</p><p class="hint" role="status" *ngIf="notice()">{{notice()}}</p>
  <div class="app-dns-tools">
   <label class="rounded-search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="7" /><path d="m15 15 6 6" /></svg><input id="app-domain-search" [(ngModel)]="search" [placeholder]="selectedPath()?'Search domains':'Search applications'" [attr.aria-label]="selectedPath()?'Search app domains':'Search applications'"></label>
   <div class="segmented" *ngIf="selectedPath()" role="group" aria-label="DNS decision filter"><button *ngFor="let option of outcomes" (click)="outcome=option" [attr.aria-pressed]="outcome===option">{{option}}</button></div>
  </div>
  <ng-container *ngIf="data() as d">
   <details class="app-coverage" *ngIf="showCoverage" open><summary>Coverage & details</summary>
    <p>{{d.coverage}}</p><p *ngIf="!d.provider_bound">Select this host's Control D endpoint in Collection settings to correlate provider decisions.</p>
    <p>Unassigned process observations: {{d.source_status.unassigned ?? 'Unknown'}} · Lost: {{d.source_status.lost ?? 'Unknown'}} · Source errors: {{d.source_status.errors ?? 'Unknown'}}</p>
    <p>{{d.start}} → {{d.end}} · revision {{d.revision}}</p>
    <p *ngIf="d.selected">{{d.selected.path}}</p>
    <button (click)="confirmDelete=true">Delete local app DNS history…</button>
   </details>
   <ng-container *ngIf="!selectedPath();else diagnosis">
    <div class="table-scroll"><table class="app-domain-table" id="app-dns-apps"><thead><tr><th>Application</th><th>IN</th><th>OUT</th><th>DNS observations</th><th>Blocked ≈</th><th>Hourly traffic</th><th><span class="sr-only">Diagnosis</span></th></tr></thead><tbody>
     <tr *ngFor="let app of apps()"><td><button class="identity-link" [title]="app.path||'Unassigned'" [disabled]="!app.path" (click)="select(app.path)">{{app.name}}</button><small *ngIf="!app.path">Traffic without an executable identity</small></td><td>{{format(app.inbound)}}</td><td>{{format(app.outbound)}}</td><td>{{app.queries}}</td><td>{{app.blocked}}</td>
      <td><svg class="app-sparkline" viewBox="0 0 120 28" role="img" [attr.aria-label]="'Hourly observed traffic for '+app.name"><rect *ngFor="let bar of bars(app)" [attr.x]="bar.x" [attr.y]="28-bar.height" width="3" [attr.height]="bar.height" /></svg></td>
      <td><button class="icon-button" [disabled]="!app.path" (click)="select(app.path)" [attr.aria-label]="'Diagnose '+app.name" title="App diagnosis"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10v1" /></svg></button></td></tr>
    </tbody></table></div><p *ngIf="!apps().length&&!busy()">No observed apps in this window. Enable analytics in Preferences to collect future activity.</p>
   </ng-container>
   <ng-template #diagnosis>
    <ng-container *ngIf="d.selected as app;else noApp">
     <div class="app-totals"><div><span>IN</span><strong>{{format(app.inbound)}}</strong></div><div><span>OUT</span><strong>{{format(app.outbound)}}</strong></div><div><span>DNS observations</span><strong>{{app.queries}}</strong></div><div><span>Blocked ≈</span><strong>{{app.blocked}}</strong></div></div>
     <details class="app-hourly"><summary>Hourly traffic · GlassWire observations</summary><svg viewBox="0 0 120 28" role="img" aria-label="Hourly app traffic concentration"><rect *ngFor="let bar of bars(app)" [attr.x]="bar.x" [attr.y]="28-bar.height" width="3" [attr.height]="bar.height" /></svg>
      <div class="table-scroll"><table><thead><tr><th>Hour</th><th>IN</th><th>OUT</th></tr></thead><tbody><tr *ngFor="let hour of hours(app)"><td>{{time(hour.at)}}</td><td>{{format(hour.inbound)}}</td><td>{{format(hour.outbound)}}</td></tr></tbody></table></div></details>
     <div class="table-scroll"><table class="app-domain-table" id="app-dns-domains"><thead><tr><th><button (click)="sort=sort==='name'?'count':'name'">{{sort==='name'?'Domain A–Z ↑':'Most observed ↓'}}</button></th><th>Latest decision</th><th>Observations</th><th>Blocked ≈</th><th>Last seen</th></tr></thead><tbody>
      <ng-container *ngFor="let domain of domains()"><tr><td><button class="identity-link" (click)="expanded=expanded===domain.name?'':domain.name" [attr.aria-expanded]="expanded===domain.name">{{domain.name}}</button></td><td><span [class.dns-blocked]="domain.outcome==='blocked'">{{label(domain.outcome)}}{{domain.outcome==='unknown'?'':' ≈'}}</span></td><td>{{domain.count}}</td><td>{{domain.blocked}}</td><td><time [title]="time(domain.last)">{{relative(domain.last)}}</time></td></tr>
       <tr *ngIf="expanded===domain.name"><td colspan="5"><p>First seen: {{time(domain.first)}}. App lookup is observed; provider decisions are name/type/time correlations.</p><p *ngIf="domain.evidence_truncated">Showing the first 50 observations; export includes this app's complete selected observations.</p>
        <div class="table-scroll"><table><thead><tr><th>Time</th><th>DNS result</th><th>Decision evidence</th><th>Process instance</th></tr></thead><tbody><tr *ngFor="let fact of domain.evidence"><td>{{time(fact.at)}}</td><td>{{fact.status===0?'Resolved':'Resolution failed · '+fact.status}}</td><td>{{fact.provider_matches}} provider candidates · {{fact.provider_reasons.join(', ')||'No policy evidence'}}</td><td>PID {{fact.process.pid}} · {{fact.process.created}}</td></tr></tbody></table></div></td></tr>
      </ng-container></tbody></table></div><p *ngIf="!domains().length">No matching app-owned DNS observations. This does not mean the app made no requests.</p>
     <details><summary>Observed IP destinations</summary><div class="table-scroll"><table><thead><tr><th>Destination IP</th><th>IN</th><th>OUT</th></tr></thead><tbody><tr *ngFor="let row of d.destinations"><td>{{row.ip}}</td><td>{{format(row.inbound)}}</td><td>{{format(row.outbound)}}</td></tr></tbody></table></div><p class="hint">Measured IP traffic is separate from app DNS observations. Shared IPs do not prove exact domain usage.</p></details>
     <details><summary>Estimated domain traffic · equal weights</summary><p class="hint">{{d.estimate_method}}. Unmatched: {{format(d.unmatched_bytes)}}.</p><div class="table-scroll"><table><thead><tr><th>Domain candidate</th><th>Estimated IN</th><th>Estimated OUT</th></tr></thead><tbody><tr *ngFor="let row of d.estimated_domains"><td>{{row.domain}}</td><td [title]="row.inbound.numerator+'/'+row.inbound.denominator+' bytes'">≈ {{fraction(row.inbound)}}</td><td [title]="row.outbound.numerator+'/'+row.outbound.denominator+' bytes'">≈ {{fraction(row.outbound)}}</td></tr></tbody></table></div></details>
    </ng-container><ng-template #noApp><p>No retained observations for this app in the selected window.</p></ng-template>
   </ng-template>
  </ng-container>
  <dialog [open]="confirmDelete" *ngIf="confirmDelete" aria-labelledby="delete-app-dns-title"><h2 id="delete-app-dns-title">Delete local app DNS history?</h2><p>Provider and GlassWire history remain unchanged.</p><div class="actions"><button (click)="confirmDelete=false">Cancel</button><button (click)="remove()">Delete</button></div></dialog>
 </section>`})
export class AppDns implements OnInit {
 @Input() initialPath:string|null=null;
 data=signal<AppRead|null>(null);busy=signal(false);error=signal('');notice=signal('');selectedPath=signal<string|null>(null);
 days=1;search='';outcome='All';outcomes=['All','Blocked','Allowed','Unknown'];sort='count';expanded='';confirmDelete=false;showCoverage=false;
 format=bytes;private generation=0;private queryWindow:{start:string;end:string}|null=null;
 sourceLabel(state:string){return state==='observing'?'Recording':state==='disabled'?'Recording off':state==='starting'?'Starting':'Unavailable'}
 fraction(value:Row){return bytes(exact(value['numerator'])/exact(value['denominator']))}
 ngOnInit(){this.selectedPath.set(this.initialPath);void this.load(true)}
 apps(){const search=this.search.toLowerCase();return this.data()?.apps.filter(a=>(a.name+' '+(a.path||'')).toLowerCase().includes(search))||[]}
 domains(){return [...(this.data()?.selected?.['domains']||[])].filter(d=>d.name.toLowerCase().includes(this.search.toLowerCase())&&(this.outcome==='All'||d[this.outcome.toLowerCase()]>0)).sort((a,b)=>this.sort==='name'?a.name.localeCompare(b.name):b.count-a.count||a.name.localeCompare(b.name))}
 async select(path:string|null){this.selectedPath.set(path);this.data.set(null);this.search='';this.outcome='All';this.expanded='';await this.load(false)}
 async load(newWindow=false){const generation=++this.generation;this.busy.set(true);this.error.set('');
  const until=newWindow||!this.queryWindow?new Date().toISOString():this.queryWindow.end;
  const start=newWindow||!this.queryWindow?new Date(Date.parse(until)-this.days*86400000).toISOString():this.queryWindow.start;
  this.queryWindow={start,end:until};if(newWindow)this.data.set(null);
  try{const value=await command<AppRead>('app-dns-read',{start,end:until,...(this.selectedPath()?{path:this.selectedPath()}: {})});if(generation===this.generation)this.data.set(value)}
  catch(e){if(generation===this.generation)this.error.set((e as Error).message)}finally{if(generation===this.generation)this.busy.set(false)}}
 async export(){const d=this.data();if(!d||!this.selectedPath())return;this.busy.set(true);try{const r=await command<Row>('app-dns-export',{start:d.start,end:d.end,path:this.selectedPath(),revision:d.revision,format:'json'});this.notice.set(r['cancelled']?'Export cancelled.':'Saved '+r['name'])}catch(e){this.error.set((e as Error).message)}finally{this.busy.set(false)}}
 async remove(){this.confirmDelete=false;this.busy.set(true);try{await command('app-dns-delete',{confirm:true});this.data.set(null)}catch(e){this.error.set((e as Error).message)}finally{this.busy.set(false)}await this.load(true)}
 hours(app:Row):Row[]{return Object.entries(app['hours']).map(([at,value])=>({at:Number(at),...(value as Row)}))}
 bars(app:Row){const d=this.data();if(!d)return [];const start=Date.parse(d.start)*1000,end=Date.parse(d.end)*1000;const count=24;const totals=Array<bigint>(count).fill(0n);
  for(const h of this.hours(app)){const i=Math.min(count-1,Math.max(0,Math.floor((h.at-start)/(end-start)*count)));totals[i]+=exact(h['inbound'])+exact(h['outbound'])}
  const max=totals.reduce((a,b)=>a>b?a:b,0n);return totals.map((n,i)=>({x:i*5,height:max?Number(n*26n/max):0}))}
 time(at:number){return new Date(at/1000).toLocaleString()}
 relative(at:number){const seconds=Math.max(0,Math.floor((Date.now()-at/1000)/1000));return seconds<60?'Just now':seconds<3600?Math.floor(seconds/60)+'m ago':seconds<86400?Math.floor(seconds/3600)+'h ago':Math.floor(seconds/86400)+' days ago'}
 label(outcome:string){return outcome==='blocked'?'Blocked':outcome==='allowed'?'Allowed':'Unknown'}
}
