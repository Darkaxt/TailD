// SPDX-License-Identifier: GPL-3.0-only
import {Component, signal, computed, OnDestroy} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {DashboardWidgetComponent} from './portmaster/panel';
import {SfngToggleSwitchComponent} from './portmaster/toggle';
import {command} from './bridge';
import {BrandMark} from './brand-mark';

interface Source {[key:string]:unknown;state:string;last_success_utc?:string;status?:number}
interface Settings {traffic:boolean;dns:boolean;traffic_seconds:number;dns_seconds:number;
  host_scope:string;provider:Provider|null}
interface Provider {account_scope:string;endpoint:string;account_type:string;instance:string;organization?:string}
export interface State {state:string;sources:Record<string,Source>;settings:Settings;queue_depth:number}

@Component({selector:'taild-collection',standalone:true,
  imports:[CommonModule,FormsModule,DashboardWidgetComponent,SfngToggleSwitchComponent,BrandMark],
  template:`
    <section id="collection-window" [attr.aria-busy]="busy()">
      <header><div><div class="eyebrow product-brand"><taild-brand-mark brand="tailscale" /><span>TailD / Settings</span></div><h2 class="collection-title">Collection</h2>
        <p>Local history. Explicit opt-in. Your network stays unchanged.</p></div>
        <span id="collector-status" role="status" class="badge" [class.good]="state()?.state==='collecting'"
          [class.warn]="isWarning(state()?.state)">{{state()?.state || 'Connecting'}}</span></header>
      <div *ngIf="error()" id="collection-error" class="error" role="alert">{{error()}}</div>
      <div class="grid" *ngIf="state() as current">
        <app-dashboard-widget label="Continuous collection">
          <div class="row"><div><div class="row-title">Application traffic</div>
            <p>Read GlassWire’s existing traffic buckets. No packet capture or firewall changes.</p></div>
            <sfng-toggle name="Collect application traffic" controlId="traffic-toggle"
              [ngModel]="current.settings.traffic" (ngModelChange)="configure({traffic:$event})"
              [disabled]="busy()" /></div>
          <div class="row"><div><div class="row-title">DNS activity</div>
            <p>Read Control D activity for the explicitly selected endpoint. A READ token is required.</p></div>
            <sfng-toggle name="Collect DNS activity" controlId="dns-toggle"
              [ngModel]="current.settings.dns" (ngModelChange)="configure({dns:$event})"
              [disabled]="busy() || !current.settings.provider" /></div>
          <div class="actions">
            <button id="pause-resume" class="primary" [disabled]="busy() || !enabled()" (click)="run(current.state==='paused'?'resume':'pause')">
              {{current.state==='paused'?'Resume collection':'Pause collection'}}</button>
            <button id="refresh" [disabled]="busy() || !enabled() || current.state==='paused'" (click)="run('refresh')">Refresh now</button>
          </div><p class="hint">Changes save automatically. Pause stops new reads; an active transaction finishes safely.</p>
        </app-dashboard-widget>
        <app-dashboard-widget label="Sources & health">
          <div class="status-table" *ngFor="let source of sourceNames">
            <div><div class="row-title provider-brand"><taild-brand-mark brand="controld" *ngIf="source==='dns'" /><taild-brand-mark brand="tailscale" *ngIf="source==='context'" />{{source==='traffic'?'GlassWire':source==='dns'?'Control D':'TailDNS context'}}</div>
              <p class="hint" *ngIf="current.sources[source]?.last_success_utc as success">Last read {{success}}</p></div>
            <span [attr.id]="source+'-status'" class="badge" [class.good]="current.sources[source]?.state==='collecting'"
              [class.warn]="isWarning(current.sources[source]?.state)">{{current.sources[source]?.state || 'Unavailable'}}</span>
          </div><p class="hint">A successful read is not proof of complete history. Coverage accompanies analytics queries.</p>
        </app-dashboard-widget>
        <app-dashboard-widget label="Sampling & identity">
          <div class="fields"><label class="field">Traffic cadence (seconds)
            <input id="traffic-cadence" type="number" min="10" max="86400" [disabled]="busy()"
              [ngModel]="current.settings.traffic_seconds" (change)="numberSetting('traffic_seconds',$event,10)"></label>
            <label class="field">DNS cadence (seconds)
            <input id="dns-cadence" type="number" min="60" max="86400" [disabled]="busy()"
              [ngModel]="current.settings.dns_seconds" (change)="numberSetting('dns_seconds',$event,60)"></label>
            <label class="field">Local host scope
              <input id="host-scope" maxlength="128" [disabled]="busy()" [ngModel]="current.settings.host_scope"
                (change)="textSetting($event)"></label></div>
          <p class="hint">Missed opportunities coalesce. Reads never overlap or get killed to meet cadence.</p>
        </app-dashboard-widget>
        <app-dashboard-widget label="Control D binding · read only" brand="controld">
          <div class="fields"><label class="field">Account scope
            <input id="provider-account" maxlength="128" [(ngModel)]="provider.account_scope" (blur)="bindProvider()" [disabled]="busy()"></label>
            <label class="field">Endpoint ID
            <input id="provider-endpoint" maxlength="128" [(ngModel)]="provider.endpoint" (blur)="bindProvider()" [disabled]="busy()"></label>
            <label class="field">Account type
              <select id="provider-type" [(ngModel)]="provider.account_type" (change)="bindProvider()" [disabled]="busy()">
                <option value="personal">Personal</option><option value="organization">Organization</option></select></label>
            <label class="field">Activity instance
              <input id="provider-instance" maxlength="128" [(ngModel)]="provider.instance" (blur)="bindProvider()" [disabled]="busy()"></label>
            <label class="field" *ngIf="provider.account_type==='organization'">Organization
              <input id="provider-org" maxlength="128" [(ngModel)]="provider.organization" (blur)="bindProvider()" [disabled]="busy()"></label>
          </div><p class="hint">Valid, complete binding fields autosave on leaving the field. Endpoint scope does not prove host attribution.</p>
          <label class="field">READ API token (optional if already in your Windows vault)
            <input id="read-token" type="password" autocomplete="off" [(ngModel)]="token" [disabled]="busy()"></label>
          <label><input id="read-confirm" type="checkbox" style="width:auto" [(ngModel)]="readOnly"> This token has READ permissions only</label>
          <label><input id="persist-token" type="checkbox" style="width:auto" [(ngModel)]="persist"> Save in my Windows credential vault</label>
          <div class="actions"><button id="use-token" class="primary" (click)="useToken()" [disabled]="busy() || !token || !readOnly">Use READ token</button>
            <button id="remove-token" (click)="removeToken()" [disabled]="busy()">Remove local credential</button></div>
        </app-dashboard-widget>
        <app-dashboard-widget label="Window & collector lifecycle" class="wide">
          <div class="row"><div><div class="row-title">{{enabled()?'Collection continues when this window closes':'Nothing collects while disabled'}}</div>
            <p>Reopen TailD to return to these controls. Stop explicitly ends the collector, without deleting history or changing saved opt-in.</p></div>
            <button id="stop-collector" [disabled]="busy()" (click)="stop()">Stop collector & close</button></div>
        </app-dashboard-widget>
      </div>
      <footer><span>Owner-only local history · No provider writes</span><span id="autosave-status" role="status">{{busy()?'Applying…':'Settings save automatically'}}</span></footer>
    </section>`})
export class Collection implements OnDestroy {
  state=signal<State|null>(null);busy=signal(false);error=signal('');
  enabled=computed(()=>!!(this.state()?.settings.traffic||this.state()?.settings.dns));
  sourceNames=['traffic','dns','context'];
  provider:Provider={account_scope:'',endpoint:'',account_type:'personal',instance:''};
  token='';readOnly=false;persist=false;private disposed=false;private healthTimer?:number;
  constructor(){void this.load()}
  async load(){await this.run('state');this.provider={...(this.state()?.settings.provider||this.provider)};
    // This is a diagnostic health cadence, not synchronization or cancellation.
    // It never starts acquisition, overlaps operations, or classifies an ongoing read.
    this.scheduleHealth();}
  scheduleHealth(){if(this.disposed)return;this.healthTimer=window.setTimeout(async()=>{
    if(!this.busy()){try{this.state.set(await command<State>('state'))}catch(e){this.error.set((e as Error).message)}}
    this.scheduleHealth();},5000)}
  async run(op:string,body:unknown={}){if(this.busy())return;this.busy.set(true);this.error.set('');
    try{this.state.set(await command<State>(op,op==='refresh'?{wait:false}:body))}catch(e){this.error.set((e as Error).message)}finally{this.busy.set(false)}}
  configure(body:Partial<Settings>){return this.run('configure',body)}
  numberSetting(key:'traffic_seconds'|'dns_seconds',event:Event,min:number){const value=Number((event.target as HTMLInputElement).value);
    if(!Number.isInteger(value)||value<min||value>86400){this.error.set(`Use a whole number from ${min} to 86400 seconds.`);return}
    void this.configure({[key]:value})}
  textSetting(event:Event){const value=(event.target as HTMLInputElement).value.trim();if(value)void this.configure({host_scope:value})}
  bindProvider(){if(!this.provider.account_scope||!this.provider.endpoint||!this.provider.instance||
    (this.provider.account_type==='organization'&&!this.provider.organization))return;
    const binding={...this.provider};if(binding.account_type==='personal')delete binding.organization;
    if(JSON.stringify(binding)!==JSON.stringify(this.state()?.settings.provider))void this.configure({provider:binding})}
  async useToken(){if(this.busy())return;const token=this.token;this.token='';this.busy.set(true);this.error.set('');
    try{await command('credential',{token,confirm_read_only:this.readOnly,persist:this.persist});this.state.set(await command<State>('state'))}
    catch(e){this.error.set((e as Error).message)}finally{this.busy.set(false)}}
  async stop(){if(this.busy())return;this.busy.set(true);try{await command('shutdown')}catch(e){this.error.set((e as Error).message);this.busy.set(false)}}
  async removeToken(){if(this.busy())return;this.busy.set(true);try{await command('credential-remove');this.token=''}
    catch(e){this.error.set((e as Error).message)}finally{this.busy.set(false)}}
  isWarning(value?:string){return !!value&&!['collecting','disabled','paused','starting','point-observation'].includes(value)}
  ngOnDestroy(){this.disposed=true;window.clearTimeout(this.healthTimer)}
}
