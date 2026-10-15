// SPDX-License-Identifier: GPL-3.0-only
import {Component,OnDestroy,signal} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {command} from './bridge';
import {DashboardWidgetComponent} from './portmaster/panel';
import {Evidence} from './evidence';
import {resolutionReason,resolutionCategories} from './resolution-reason';

type RecordValue=Record<string,any>;
@Component({selector:'taild-control-d',standalone:true,
  imports:[CommonModule,FormsModule,DashboardWidgetComponent,Evidence],template:`
  <section class="incident-workspace" aria-label="Control D incident management" [attr.aria-busy]="busy()">
    <div class="error" role="alert" *ngIf="error()">{{error()}}</div>
    <div class="incident-progress" role="status" *ngIf="busy()"><span class="progress-pulse"></span>{{activity()}}</div>
    <div role="status" class="hint" *ngIf="notice()">{{notice()}}</div>
    <app-dashboard-widget label="Control D · incident workspace" brand="controld" id="management-binding">
      <div class="incident-binding">
        <label>Endpoint<select id="management-endpoint" [(ngModel)]="endpoint" (change)="load()" [disabled]="busy()">
          <option *ngFor="let d of devices()" [value]="d.PK">{{d.name || d.PK}} · {{d.PK}}</option></select></label>
        <div><span class="eyebrow">Enforced profile</span><h2>{{snapshot()?profileName():'Not loaded'}}</h2><small>{{snapshot()?.profile}}</small></div>
        <button id="management-reload" (click)="load()" [disabled]="busy()">Reload policy</button>
      </div>
      <p *ngIf="!snapshot()&&!busy()">Configure a READ credential and endpoint binding in Settings, then reload this page.</p>
      <details *ngIf="snapshot()" class="incident-scope-details"><summary>Shared profile · {{affected().length}} affected endpoint(s)</summary><p class="hint">Profile policy affects every endpoint below, not only this computer. Endpoint selection here does not change DNS collection or your resolver.</p>
        <div class="incident-endpoints"><span class="filter-pill" *ngFor="let d of affected()">{{d.name}}</span></div>
        <p class="hint">Browsing uses READ access. Explicit changes use the separate Write credential. Allow creates a Bypass rule and can override filter blocks.</p></details>
    </app-dashboard-widget>
    <app-dashboard-widget label="Recent DNS · incident resolutions" brand="controld" id="management-recent" *ngIf="snapshot()">
      <div class="incident-recent-controls"><label>Search resolutions<input id="incident-dns-search" [ngModel]="dnsSearch" placeholder="Domain / decision" (ngModelChange)="searchChanged($event)"></label>
        <label class="incident-confirm"><input type="checkbox" [(ngModel)]="observe"> Follow recent activity</label>
        <button id="incident-dns-refresh" [disabled]="reading()||busy()" (click)="recent()">{{reading()?'Reading…':'Refresh DNS'}}</button>
        <span class="badge" [class.good]="liveState()==='connected'">Live stream: {{liveState()}}</span></div>
      <p class="hint">Latest 100 stored observations in the last 15 minutes for the selected endpoint. Streaming follows the collection binding, not this selection. Gaps do not mean zero activity.</p>
      <div class="table-scroll incident-table"><table><thead><tr><th>Time</th><th>Question</th><th>Decision / reason</th><th>Profile</th><th>Incident actions</th></tr></thead><tbody>
        <tr *ngFor="let r of recentRows()"><td>{{time(r.timestamp)}}</td><td>{{r.question}} <small>{{r.type}}</small></td><td><strong>{{r.outcome}}</strong><p>{{reason(r)}}</p>
          <details><summary>Decision details</summary><p class="hint">Classification: {{categories(r).join(', ')||'Not supplied'}}</p><p class="hint">Category labels describe the domain; the provider trigger above identifies the decision cause. Names from current policy are display labels, not historical policy proof.</p><taild-evidence [data]="r.fact" /></details></td><td>{{r.profile}}</td>
          <td class="actions"><button (click)="incident(r,0)" [disabled]="busy()||!!preview()||r.profile!==snapshot()?.profile">Block</button>
            <button (click)="incident(r,1)" [disabled]="busy()||!!preview()||r.profile!==snapshot()?.profile">Allow</button>
            <button (click)="editQuestion(r)" [disabled]="busy()||!!preview()||r.profile!==snapshot()?.profile">Edit rule</button></td></tr>
      </tbody></table></div>
      <p class="empty-state" *ngIf="!recentRows().length&&!reading()">No stored resolutions in this endpoint's recent window. Check its last activity and the collection binding; this is not proof of no DNS traffic.</p>
      <p class="hint">Actions are disabled when a historical event's profile differs from the currently enforced profile.</p>
    </app-dashboard-widget>
    <app-dashboard-widget *ngIf="preview() as p" label="Review policy change" id="management-preview">
      <h2>{{p.change.delete?'Delete rule':p.change.kind==='rule'?(p.change.do===1?'Allow · explicit Bypass':'Block'):'Update '+p.change.kind}} · {{p.change.hostname || p.change.id}}</h2>
      <p>Profile {{p.profile}} · {{p.affected_endpoints.length}} affected endpoint(s)</p>
      <div class="incident-endpoints"><span class="filter-pill" *ngFor="let d of p.affected_endpoints">{{d.name}}</span></div>
      <taild-evidence [data]="p.change" />
      <label class="incident-confirm"><input type="checkbox" id="management-confirm" [(ngModel)]="confirmed" [disabled]="busy()"> I confirm this shared-profile change.</label>
      <div class="actions"><button id="management-apply" (click)="apply()" [disabled]="busy()||!confirmed">Apply change</button>
        <button (click)="cancel()" [disabled]="busy()">Cancel</button></div>
    </app-dashboard-widget>
    <nav class="incident-tabs" aria-label="Profile sections" *ngIf="snapshot()">
      <button *ngFor="let t of tabs" [attr.aria-pressed]="tab()===t" [class.active]="tab()===t" (click)="tab.set(t)">{{t}}</button>
    </nav>
    <app-dashboard-widget *ngIf="snapshot()" [label]="tab()" brand="controld" id="management-policy">
      <fieldset class="incident-controls" [disabled]="busy()||!!preview()">
        <ng-container *ngIf="tab()==='Rules'">
          <form class="incident-rule-form" (ngSubmit)="prepareRule()">
            <label>Hostname<input id="incident-hostname" name="hostname" [(ngModel)]="hostname" placeholder="example.com" maxlength="253" required></label>
            <label>Action<select name="ruleAction" [(ngModel)]="ruleAction"><option [ngValue]="-1" disabled>Choose Block or Bypass</option><option [ngValue]="0">Block</option><option [ngValue]="1">Allow · Bypass</option></select></label>
            <label>Comment<input name="comment" [(ngModel)]="comment" maxlength="64"></label>
            <button id="incident-preview-rule" type="submit" [disabled]="!hostname.trim()||ruleAction<0">Preview rule</button>
          </form>
          <label>Find rules<input id="management-rule-search" [(ngModel)]="ruleSearch" placeholder="Search hostnames"></label>
          <p class="hint" *ngIf="resourceState('rules')!=='available'">{{resourceState('rules')}} · rules cannot be edited.</p>
          <div class="table-scroll incident-table"><table><thead><tr><th>Hostname</th><th>Action</th><th>Enabled</th><th>Incident actions</th></tr></thead><tbody>
            <tr *ngFor="let r of rules()"><td>{{r.PK}}</td><td>{{actionName(r.action?.do)}}</td><td>{{r.action?.status===1?'Yes':'No'}}</td><td class="actions">
              <button (click)="editRule(r)">{{r.action?.do>1?'Replace action…':'Edit'}}</button><button [disabled]="r.action?.do!==0&&r.action?.do!==1" (click)="prepare({kind:'rule',hostname:r.PK,do:r.action?.do,status:r.action?.status===1?0:1,comment:r.comment||''})">{{r.action?.status===1?'Disable':'Enable'}}</button>
              <button (click)="prepare({kind:'rule',hostname:r.PK,delete:true})">Delete</button></td></tr>
          </tbody></table></div>
          <p class="hint" *ngIf="!rules().length">No matching rules in the returned policy.</p>
        </ng-container>
        <ng-container *ngIf="tab()==='Filters'">
          <p class="hint">Select a native filter level. Unsupported or external catalogs remain visible in policy evidence below.</p>
          <div class="incident-setting" *ngFor="let f of resource('filters')"><div><strong>{{f.name||f.PK}}</strong><p class="hint">{{f.description}}</p></div>
            <select [attr.aria-label]="'Level for '+(f.name||f.PK)" [(ngModel)]="f.selected"><option [value]="f.PK">{{f.PK}}</option><option *ngFor="let l of f.levels||[]" [value]="l.name">{{l.title||l.name}}</option></select>
            <span class="badge">{{f.status===1?'Enabled':'Disabled'}}</span>
            <button (click)="prepare({kind:'filter',id:f.selected||f.action?.lvl||f.PK,status:1})">Enable selected</button>
            <button (click)="prepare({kind:'filter',id:f.action?.lvl||f.PK,status:0})">Disable</button></div>
          <p class="hint" *ngIf="resourceState('filters')!=='available'">{{resourceState('filters')}} · filter changes unavailable.</p>
        </ng-container>
        <ng-container *ngIf="tab()==='Services'">
          <label>Find services<input [(ngModel)]="serviceSearch" placeholder="Search services"></label>
          <div class="incident-setting" *ngFor="let s of services()"><div><strong>{{s.name||s.PK}}</strong><p class="hint">{{s.category}} · {{actionName(s.action?.do)}} · {{s.action?.status===1?'Enabled':'Disabled'}}</p></div>
            <button (click)="prepare({kind:'service',id:s.PK,status:1,do:0})">Block</button>
            <button (click)="prepare({kind:'service',id:s.PK,status:1,do:1})">Allow · Bypass</button>
            <button (click)="prepare({kind:'service',id:s.PK,status:0,do:s.action?.do===1?1:0})" [disabled]="s.action?.do>1">Disable</button></div>
          <p class="hint" *ngIf="resourceState('services')!=='available'">{{resourceState('services')}} · service changes unavailable.</p>
        </ng-container>
        <ng-container *ngIf="tab()==='Profile Options'">
          <p class="hint">Provider option identifiers and current values. Preview changes before applying; optional values are sent exactly as entered.</p>
          <div class="incident-setting" *ngFor="let o of resource('options')"><div><strong>{{o.title||o.name||o.PK}}</strong><p class="hint">{{o.description}}</p><p class="hint">Current value: {{o.value??'Provider default / not explicitly configured'}}</p></div>
            <label *ngIf="o.type!=='toggle'">New value<input [(ngModel)]="o.editValue" [attr.aria-label]="'Value for '+o.PK" maxlength="1024"></label>
            <button (click)="prepare(o.type==='toggle'?{kind:'option',id:o.PK,status:1}:{kind:'option',id:o.PK,status:1,value:o.editValue})">Enable / set</button>
            <button (click)="prepare({kind:'option',id:o.PK,status:0})">Disable</button></div>
          <p class="hint" *ngIf="resourceState('options')!=='available'">{{resourceState('options')}} · option changes unavailable.</p>
        </ng-container>
      </fieldset>
      <details><summary>Provider policy evidence · unavailable categories included</summary><taild-evidence [data]="snapshot()?.resources" /></details>
    </app-dashboard-widget>
    <details *ngIf="snapshot()"><summary>Captured policy history</summary><button [disabled]="busy()" (click)="history()">Read retained snapshots</button>
      <taild-evidence [data]="policyHistory()" /></details>
  </section>`})
export class ControlDManagement implements OnDestroy {
  tabs=['Rules','Filters','Services','Profile Options'];tab=signal('Rules');snapshot=signal<RecordValue|null>(null);
  preview=signal<RecordValue|null>(null);busy=signal(false);reading=signal(false);error=signal('');notice=signal('');activity=signal('');
  recentRows=signal<RecordValue[]>([]);liveState=signal('not observed');policyHistory=signal<RecordValue|null>(null);
  endpoint='';hostname='';ruleAction=0;comment='';ruleSearch='';serviceSearch='';dnsSearch='';confirmed=false;observe=true;
  private disposed=false;private timer?:number;private generation=0;private pendingRecent=false;private knownDevices:RecordValue[]=[];
  constructor(){void this.load();this.schedule()}
  devices(){return this.knownDevices}
  affected(){return this.snapshot()?.affected_endpoints||[]}
  profileName(){return (this.snapshot()?.resources?.profiles?.data?.profiles||[]).find((p:RecordValue)=>p.PK===this.snapshot()?.profile)?.name||this.snapshot()?.profile}
  resourceState(kind:string){return this.snapshot()?.resources?.[kind]?.state||'unavailable'}
  resource(kind:string):RecordValue[]{return this.resourceState(kind)==='available'?(this.snapshot()?.resources?.[kind]?.data?.[kind]||[]):[]}
  rules(){return this.resource('rules').filter(r=>r.PK.toLowerCase().includes(this.ruleSearch.toLowerCase()))}
  services(){return this.resource('services').filter(r=>(r.name||r.PK).toLowerCase().includes(this.serviceSearch.toLowerCase()))}
  actionName(value:unknown){return ({0:'Block',1:'Bypass',2:'Spoof',3:'Redirect'} as Record<string,string>)[String(value)]||'Unknown'}
  reason(row:RecordValue){return resolutionReason(row,row.profile===this.snapshot()?.profile?this.resource('filters'):[],row.profile===this.snapshot()?.profile?this.resource('services'):[])}
  categories(row:RecordValue){return resolutionCategories(row)}
  time(value:number){return new Date(value/1000).toLocaleTimeString()}
  private accept(s:RecordValue){
    for(const o of s.resources?.options?.data?.options||[])o.editValue=String(o.value??'');
    for(const f of s.resources?.filters?.data?.filters||[])f.selected=f.action?.lvl||f.PK;
    this.knownDevices=s.resources?.endpoints?.data?.devices||this.knownDevices;
    this.snapshot.set(s);this.endpoint=s.endpoint;
  }
  async load(){if(this.busy())return;this.busy.set(true);this.activity.set('Reading current Control D policy…');this.error.set('');this.preview.set(null);this.confirmed=false;this.generation++;
    this.snapshot.set(null);this.recentRows.set([]);
    try{const s=await command<RecordValue>('management-read',this.endpoint?{endpoint:this.endpoint}:{});if(!this.disposed)this.accept(s)}
    catch(e){if(!this.disposed)this.error.set((e as Error).message)}finally{this.busy.set(false)}
    if(!this.disposed&&this.snapshot())await this.recent();
  }
  async prepare(change:RecordValue){if(this.busy()||this.preview()||!this.snapshot()||this.endpoint!==this.snapshot()?.endpoint)return;this.busy.set(true);this.activity.set('Checking account, current policy and affected endpoints…');this.error.set('');this.notice.set('');
    try{const p=await command<RecordValue>('management-prepare',{endpoint:this.endpoint,change});if(!this.disposed){this.preview.set(p);this.confirmed=false;requestAnimationFrame(()=>document.getElementById('management-confirm')?.focus())}}
    catch(e){if(!this.disposed)this.error.set((e as Error).message)}finally{this.busy.set(false)}
  }
  prepareRule(){void this.prepare({kind:'rule',hostname:this.hostname.trim(),do:this.ruleAction,status:1,comment:this.comment})}
  editRule(r:RecordValue){this.hostname=r.PK;this.ruleAction=r.action?.do===0?0:r.action?.do===1?1:-1;this.comment=r.comment||'';this.tab.set('Rules');requestAnimationFrame(()=>document.getElementById('incident-hostname')?.focus())}
  editQuestion(r:RecordValue){this.editRule(this.resource('rules').find(rule=>rule.PK===r.question)||{PK:r.question,action:{do:1}})}
  incident(r:RecordValue,action:number){void this.prepare({kind:'rule',hostname:r.question,do:action,status:1,comment:'TailD incident'})}
  async apply(){const p=this.preview();if(!p||!this.confirmed||this.busy())return;this.busy.set(true);this.activity.set('Applying once, then reading back policy…');this.error.set('');
    try{const result=await command<RecordValue>('management-apply',{ticket:p.ticket,confirm:true});if(!this.disposed){this.accept(result.snapshot);this.notice.set('Change applied and current policy read back.')}}
    catch(e){if(!this.disposed)this.error.set((e as Error).message)}finally{this.preview.set(null);this.confirmed=false;this.busy.set(false)}
  }
  async cancel(){if(this.busy())return;this.preview.set(null);this.confirmed=false;try{await command('management-cancel')}catch(e){this.error.set((e as Error).message)}}
  searchChanged(value:string){this.dnsSearch=value;this.recentRows.set([]);void this.recent()}
  async recent(){if(this.disposed||this.busy()||!this.snapshot())return;if(this.reading()){this.pendingRecent=true;return;}
    this.pendingRecent=false;this.reading.set(true);const generation=this.generation,endpoint=this.endpoint,search=this.dnsSearch;
    try{const end=new Date(),start=new Date(end.getTime()-900000);const result=await command<RecordValue>('view-query',{queries:[{
      kind:'dns',view:'facts',start:start.toISOString(),end:end.toISOString(),scope:{endpoint},limit:100,
      ...(search?{search}:{}),order_by:[{field:'timestamp',direction:'desc'}]}]});
      const state=await command<RecordValue>('state');if(!this.disposed&&generation===this.generation&&search===this.dnsSearch){this.recentRows.set(result.results[0].data.rows||[]);this.liveState.set(state.sources?.dns_live?.state||'not available')}}
    catch(e){if(!this.disposed&&generation===this.generation&&search===this.dnsSearch)this.error.set((e as Error).message)}finally{this.reading.set(false);if(this.pendingRecent&&!this.disposed)void this.recent()}
  }
  async history(){try{const end=new Date();const result=await command<RecordValue>('view-query',{queries:[{kind:'policy',view:'facts',start:new Date(end.getTime()-7*86400000).toISOString(),end:end.toISOString(),scope:{endpoint:this.endpoint},limit:100}]});this.policyHistory.set(result.results[0])}catch(e){this.error.set((e as Error).message)}}
  private schedule(){if(this.disposed)return;this.timer=window.setTimeout(async()=>{if(this.observe&&!document.hidden)await this.recent();this.schedule()},5000)}
  ngOnDestroy(){this.disposed=true;window.clearTimeout(this.timer)}
}
