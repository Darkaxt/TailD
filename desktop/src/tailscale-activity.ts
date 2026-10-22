// SPDX-License-Identifier: GPL-3.0-only
import {Component,Input,Output,EventEmitter,OnChanges,OnDestroy,signal} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {command} from './bridge';
import {DashboardWidgetComponent} from './portmaster/panel';
import {bytes} from './portmaster/charts';
import {relativeSeen} from './device-presentation';

interface Observation {profile:string;id?:string;name?:string;os?:string;presence?:string;observed_at?:string;last_seen?:string|null;
  type?:string;value?:any;direction?:string;peer_id?:string;started_at?:string;first_observed_at?:string;
  last_observed_at?:string;declared_bytes?:number|null;observed_bytes?:number;result?:string}
interface ActivityView {rows:Observation[];profiles:string[];truncated:boolean;enabled:boolean;
  source:{state:string;last_success_utc?:string;profile?:string};start:string;end:string}

@Component({selector:'taild-tailscale-activity',standalone:true,
  imports:[CommonModule,FormsModule,DashboardWidgetComponent],template:`
  <section id="tailscale-activity" [attr.aria-busy]="busy()">
    <div class="taildrop-primary-actions" *ngIf="view==='TailDrop'"><button id="taildrop-open-downloads" (click)="openDownloads()"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h7l2 3h9v12H3z" /></svg>Open received files</button><span class="hint">Downloads · same destination as the tray receiver</span></div>
    <div class="activity-toolbar">
      <div class="activity-opt-in"><span class="badge" [class.good]="tracking()">{{tracking()?'Analytics recording enabled':'Recording disabled · retained history'}}</span>
        <button id="activity-preferences" (click)="preferences.emit()">Preferences →</button></div>
      <span id="activity-source" class="badge" [class.good]="data()?.source?.state==='connected'" role="status">{{data()?.source?.state||'Not loaded'}}</span>
      <button id="activity-reload" class="icon-button" aria-label="Refresh Tailscale history" title="Refresh Tailscale history" (click)="load()" [attr.aria-disabled]="busy()"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5M20 12a8 8 0 1 0-2 6M20 7l-3-3" /></svg></button>
      <span *ngIf="busy()" class="activity-loading" role="status"><span class="loading-dots" aria-hidden="true"><span></span><span></span><span></span></span>Reading local history</span>
    </div>
    <p class="error" role="alert" *ngIf="error()||mutationError()">{{mutationError()||error()}}</p>
    <div class="activity-scope">
      <label>Profile<select id="activity-profile" [(ngModel)]="profile" (change)="load()"><option value="">All recorded profiles</option><option *ngFor="let p of data()?.profiles" [value]="p">{{p}}</option></select></label>
      <label>Observed within<select id="activity-period" [(ngModel)]="days" (change)="load()"><option [ngValue]="1">Last 24 hours</option><option [ngValue]="7">Last 7 days</option><option [ngValue]="30">Last 30 days · if retained</option></select></label>
      <label class="rounded-search"><span class="sr-only">Search</span><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="7" /><path d="m15 15 6 6" /></svg><input id="tailscale-history-search" [(ngModel)]="search" (keydown.enter)="applySearch()" maxlength="128" placeholder="Name or device ID · Enter"></label>
    </div>
    <label class="activity-baseline-option" *ngIf="view==='Tailscale activity'"><input id="activity-include-baselines" type="checkbox" [(ngModel)]="includeBaselines" (change)="load()">Include starting snapshots</label>
    <p class="hint" *ngIf="view==='Tailscale activity'&&!includeBaselines">Only observed changes and collection gaps are shown. An already-offline device in a starting snapshot is not new activity.</p>
    <app-dashboard-widget [label]="view==='TailDrop'?'TailDrop · daemon-reported transfers':'Tailscale activity · observed changes'" brand="tailscale">
      <div class="table-scroll activity-table" *ngIf="data() as d">
        <table id="tailscale-history-table"><thead>
          <tr *ngIf="view==='TailDrop'"><th>File / peer</th><th>Direction</th><th>Observed bytes</th><th>Reported result</th><th>Last observed</th></tr>
          <tr *ngIf="view==='Tailscale activity'"><th>{{includeBaselines?'Snapshot / change recorded':'Change recorded'}}</th><th>Event</th><th>Details</th></tr>
        </thead><tbody>
          <ng-container *ngFor="let row of d.rows">
            <tr *ngIf="view==='TailDrop'"><td><strong>{{row.name}}</strong><small class="identity-id">{{row.peer_id||'Peer not reported'}}</small><details class="device-metadata"><summary>Details</summary><p>{{row.profile}} · started {{time(row.started_at)}}</p></details></td><td>{{row.direction==='sent'?'OUT':'IN'}}</td><td>{{format(row.observed_bytes||0)}} / {{row.declared_bytes==null?'Unknown size':format(row.declared_bytes)}}<progress *ngIf="row.declared_bytes!=null&&row.declared_bytes!>0" [value]="row.observed_bytes" [max]="row.declared_bytes" aria-label="Observed transfer bytes"></progress></td><td><span class="badge" [class.good]="row.result==='sent'||row.result==='received-by-daemon'">{{result(row.result)}}</span></td><td><time [title]="time(row.last_observed_at)">{{relative(row.last_observed_at||null,false)}}</time></td></tr>
            <tr *ngIf="view==='Tailscale activity'"><td>{{time(row.observed_at)}}</td><td><span class="badge">{{row.type}}</span><small class="identity-id">{{row.profile}}</small></td><td>{{details(row)}}</td></tr>
          </ng-container>
          <tr *ngIf="!d.rows.length"><td [attr.colspan]="view==='TailDrop'?5:3" class="activity-empty">{{view==='TailDrop'?'No transfers observed in this scope. Past transfers cannot be reconstructed.':!includeBaselines?'No changes recorded in this scope. Starting snapshots are hidden; enable Collect analytics in Preferences to record future changes.':'No observations in this scope. Enable Collect analytics in Preferences to begin; past presence is not reconstructed.'}}</td></tr>
        </tbody></table>
      </div>
      <p class="hint" *ngIf="data()?.truncated">Showing the newest 200 records. Narrow the period, profile or search.</p>
      <p class="hint" *ngIf="data()?.source?.last_success_utc">Status last read from this laptop's daemon: {{time(data()?.source?.last_success_utc)}}</p>
      <p class="hint">{{view==='TailDrop'?'Received by daemon is not proof of save to Downloads. Disappeared transfers and observation gaps remain unknown.':'Starting snapshots establish initial state, not device activity. Change timestamps are when a transition was recorded, not proof of its exact occurrence. Gaps are not uptime or offline transitions.'}}</p>
    </app-dashboard-widget>
    <details class="activity-provenance"><summary>Sources & privacy</summary><p>Tailscale supplies device presence, connection, exit-node and resolver observations, plus TailDrop metadata. GlassWire supplies application bytes. Control D supplies DNS decisions and answer geography. No Tailscale packet or per-process metrics are invented.</p><p>Metadata only: no file contents, complete file paths, private keys or authentication URLs. Existing local retention applies. Tracking continues while the window is closed if enabled.</p></details>
    <div class="actions"><button id="activity-delete" (click)="confirming.set(true)" [disabled]="busy()">Delete activity history…</button></div>
    <section *ngIf="confirming()" class="connectivity-confirm" role="group" aria-label="Delete Tailscale history"><h2>Delete all Tailscale activity history?</h2><p>Removes device, event and transfer observations for every profile. Replayed old transfers remain suppressed. VPN settings and other source history are unchanged.</p><div class="actions"><button id="activity-delete-confirm" (click)="remove()" [disabled]="busy()">Delete history</button><button (click)="confirming.set(false)">Cancel</button></div></section>
  </section>`})
export class TailscaleActivity implements OnChanges,OnDestroy {
  relative=relativeSeen;
  @Output() preferences=new EventEmitter<void>();
  @Input() view='Tailscale activity';data=signal<ActivityView|null>(null);busy=signal(false);error=signal('');mutationError=signal('');tracking=signal(false);confirming=signal(false);
  profile='';days=7;search='';includeBaselines=false;private appliedSearch='';private generation=0;private queued=false;private disposed=false;private timer?:number;
  ngOnChanges(){this.generation++;this.data.set(null);void this.load()}
  ngOnDestroy(){this.disposed=true;if(this.timer!==undefined)clearTimeout(this.timer)}
  async load(){if(this.disposed)return;if(this.busy()){this.queued=true;return}
    if(this.timer!==undefined)clearTimeout(this.timer);this.busy.set(true);this.error.set('');const version=this.generation;
    const view=this.view==='TailDrop'?'transfers':'events';
    try{const now=new Date();const d=await command<ActivityView>('activity-read',{view,profile:this.profile,search:this.appliedSearch,include_baselines:this.includeBaselines,
      start:new Date(now.getTime()-this.days*86400000).toISOString()});if(!this.disposed&&version===this.generation){this.data.set(d);this.tracking.set(d.enabled)}}
    catch(e){if(!this.disposed&&version===this.generation)this.error.set((e as Error).message)}
    finally{this.busy.set(false);if(!this.disposed){if(this.queued){this.queued=false;void this.load()}
      else this.timer=window.setTimeout(()=>void this.load(),5000)}} // Observation refresh only; never cancels an operation.
  }
  applySearch(){this.appliedSearch=this.search;this.generation++;void this.load()}
  async openDownloads(){this.mutationError.set('');try{await command('taildrop-open-downloads')}catch(e){this.mutationError.set((e as Error).message)}}
  async remove(){if(this.busy())return;this.busy.set(true);this.mutationError.set('');
    try{await command('activity-delete',{confirm:true});this.confirming.set(false)}catch(e){this.mutationError.set((e as Error).message)}finally{this.busy.set(false);await this.load()}}
  time(value?:string){return value?new Date(value).toLocaleString():'Unknown'}
  format(value:number){return bytes(value)}
  result(value?:string){return ({sent:'Sent',failed:'Failed','received-by-daemon':'Received by daemon','in-progress':'In progress',unknown:'Unknown outcome'} as Record<string,string>)[value||'']||'Unknown'}
  details(row:Observation){const v=row.value||{},c=v.current||{};
    if(row.type==='peer-presence')return `${v.name||v.id}: ${v.from} → ${v.to}`;
    if(row.type==='peer-baseline')return `${v.name||v.id}: already ${v.presence} in starting snapshot · not a device activity event`;
    if(row.type==='peer-unavailable')return `${v.name||v.id}: ${v.reason}`;
    if(row.type==='connection')return `${v.baseline?'Baseline':v.previous?.state+' →'} ${c.state}`;
    if(row.type==='exit-node')return `${v.baseline?'Baseline · ':''}${c.id||'No exit node'}`;
    if(row.type==='resolver')return `Override ${c.applied?'applied':c.configured?'saved':'off'} · fallback ${c.fallback==null?'unknown':c.fallback?'active':'inactive'} · captive portal ${c.captive_portal==null?'unknown':c.captive_portal?'active':'inactive'}`;
    return v.reason||v.coverage||'Observed change';}
}
