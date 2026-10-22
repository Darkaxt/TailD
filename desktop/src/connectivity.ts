// SPDX-License-Identifier: GPL-3.0-only
import {Component,Input,Output,EventEmitter,signal} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {command} from './bridge';
import {DashboardWidgetComponent} from './portmaster/panel';
import {SfngToggleSwitchComponent} from './portmaster/toggle';
import {BrandMark} from './brand-mark';
import {AnalyticsPreference} from './collection';
import {relativeSeen,osSymbol} from './device-presentation';

interface Preference {id:string;label:string;value:boolean;visible:boolean;editable:boolean}
interface Peer {self?:boolean;id:string;name:string;addresses:string[];online:boolean|null;exit:boolean;exit_selected:boolean;
  owner:string|null;os:string|null;last_seen:string|null;created:string|null;key_expiry:string|null;
  tags:string[];routes:string[];taildrop:'Enabled'|'Disabled'|null;taildrop_reason:string|null;ssh:string;dns_name:string|null}
interface ConnectivityState {revision:string;profile:string;account:string;state:string;device:string;addresses:string[];
  preferences:Preference[];prefs:{WantRunning:boolean;ExitNodeID:string;ExitNodeAllowLANAccess:boolean;RunExitNode:boolean};
  resolver:{Configured:boolean;Endpoint:string;Applied:boolean;CaptivePortal:boolean;Reason:string};
  self:Peer;show_admin:boolean;peers:Peer[];show_peers:boolean;show_exit:boolean;show_run_exit:boolean;show_reset:boolean;
  can_disconnect:boolean;can_exit:boolean;can_exit_lan:boolean;can_run_exit:boolean;can_reset:boolean;can_resolver:boolean}

@Component({selector:'taild-connectivity',standalone:true,imports:[CommonModule,FormsModule,DashboardWidgetComponent,SfngToggleSwitchComponent,AnalyticsPreference],template:`
  <section id="connectivity-window" class="connectivity-workspace" [attr.aria-busy]="busy()">
    <div class="connectivity-toolbar"><span class="badge" [class.good]="state()?.state==='Running'">{{state()?.state||(busy()?'Reading device…':'Unavailable')}}</span>
      <button *ngIf="state() as s" id="connectivity-toggle" class="connection-switch" role="switch" aria-label="Connect this device" [attr.aria-checked]="s.prefs.WantRunning" [class.on]="s.prefs.WantRunning" [disabled]="busy()||!s.profile||!s.can_disconnect" (click)="s.prefs.WantRunning?ask('disconnect'):edit('connected',true)"><span aria-hidden="true"></span></button>
      <div class="connection-account" *ngIf="state() as s"><strong>{{s.account || s.self.owner || 'This device'}}</strong><span class="hint">{{s.state==='Running'?'Connected':s.state==='Stopped'?'Disconnected':s.state}} · {{s.self.name}}</span></div>
      <button id="connectivity-reload" class="icon-button" (click)="load()" [disabled]="busy()" aria-label="Reload device" title="Reload device"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5M20 12a8 8 0 1 0-2 6M20 7l-3-3" /></svg></button>
      <span class="hint" role="status">{{busy()?'Reading / applying device settings…':notice()}}</span></div>
    <div *ngIf="error()" id="connectivity-error" class="error" role="alert">{{error()}}</div>
    <ng-container *ngIf="state() as s">
      <div class="grid" *ngIf="view==='Connection'">
        <app-dashboard-widget label="Network devices" brand="tailscale" class="wide" *ngIf="s.show_peers">
          <label class="search-input">Find a device<input id="device-search" [(ngModel)]="deviceSearch" placeholder="Name, owner, address or tag…"></label>
          <div class="table-scroll"><table id="connection-devices"><thead><tr><th>Device / capabilities</th><th>Addresses</th><th>Last online</th></tr></thead><tbody>
            <tr *ngFor="let peer of visiblePeers()"><td><div class="device-identity"><span class="presence-square" [class.online]="peer.online===true" [class.offline]="peer.online===false" role="img" [attr.aria-label]="presence(peer.online)" [title]="presence(peer.online)"><span></span></span><strong>{{peer.name||(peer.self?'This device':'Unnamed device')}}</strong><svg class="device-os" viewBox="0 0 24 24" role="img" [attr.aria-label]="os(peer.os).name"><title>{{os(peer.os).name}}</title><path [attr.d]="os(peer.os).path" fill="currentColor" fill-rule="evenodd" /></svg><span *ngIf="peer.self" class="badge">This device</span></div><small class="identity-id">{{peer.owner||'Owner not reported'}}</small>
              <div class="device-badges"><span class="badge" *ngIf="peer.exit">{{peer.exit_selected?'Selected exit node':'Exit node'}}</span><span class="badge" *ngIf="peer.routes.length">Subnet router</span>
                <span class="badge" *ngIf="peer.taildrop" [class.good]="peer.taildrop==='Enabled'" [title]="peer.taildrop_reason||'Current send eligibility reported by this daemon'">TailDrop · {{peer.taildrop}}</span>
                <span class="badge" *ngIf="peer.ssh==='Advertised'">SSH advertised</span><span class="badge" *ngFor="let tag of peer.tags">{{tag}}</span></div>
              <details class="device-metadata"><summary>Details</summary><dl><dt>Device ID</dt><dd>{{peer.id}}</dd><dt>DNS name</dt><dd>{{peer.dns_name||'Not reported'}}</dd>
                <dt>Registered</dt><dd>{{time(peer.created)}}</dd><dt>Key expiry</dt><dd>{{time(peer.key_expiry)}}</dd><dt>Reported subnet routes</dt><dd>{{peer.routes.join(' · ')||'None reported'}}</dd>
                <dt *ngIf="peer.taildrop">TailDrop</dt><dd *ngIf="peer.taildrop">{{peer.taildrop}}</dd><dt>SSH capability</dt><dd>{{peer.ssh}} · not a reachability test</dd></dl></details></td>
              <td><code *ngFor="let address of peer.addresses" class="device-address">{{address}}</code></td><td><time [attr.datetime]="peer.last_seen" [title]="time(peer.last_seen)">{{relative(peer.last_seen,peer.online)}}</time></td></tr></tbody></table></div>
          <p *ngIf="!visiblePeers().length" class="hint">No devices match this view.</p>
          <p class="hint">Live local-daemon inventory · independent of analytics recording. Online means connected to the control plane, not ping reachability. Client versions, detailed OS versions and signing-node roles require additional admin metadata; missing values are not disabled features.</p>
        </app-dashboard-widget>
      </div>
      <app-dashboard-widget label="Device preferences" brand="tailscale" *ngIf="view==='Preferences'">
        <ng-container *ngFor="let pref of s.preferences"><div class="row" *ngIf="pref.visible"><div><div class="row-title">{{pref.label}}</div><small class="hint" *ngIf="!pref.editable">Managed by system policy / account</small></div>
          <sfng-toggle [name]="pref.label" [controlId]="'connectivity-'+pref.id" [ngModel]="pref.value" (ngModelChange)="edit(pref.id,$event)" [disabled]="busy()||!pref.editable" /></div></ng-container>
        <taild-analytics-preference />
        <ng-container *ngIf="s.show_exit">
          <div class="row"><div><div class="row-title">Use an exit node</div><small class="hint">Route Internet traffic through a selected tailnet device.</small></div>
            <sfng-toggle name="Use an exit node" controlId="connectivity-use-exit" [ngModel]="exitEnabled||!!s.prefs.ExitNodeID" (ngModelChange)="toggleExit($event)" [disabled]="busy()||!s.can_exit" /></div>
          <div class="row" *ngIf="exitEnabled||s.prefs.ExitNodeID"><label for="connectivity-exit">Exit node</label><select id="connectivity-exit" [ngModel]="s.prefs.ExitNodeID||''" (ngModelChange)="edit('exit-node',$event)" [disabled]="busy()||!s.can_exit"><option value="" disabled>Select an exit node</option><option *ngFor="let peer of exitNodes()" [value]="peer.id">{{peer.name}}{{peer.online?'':' · offline'}}</option></select></div>
          <div class="row" *ngIf="s.prefs.ExitNodeID"><span>Allow local network access</span><sfng-toggle name="Allow local network access" controlId="connectivity-exit-lan" [ngModel]="s.prefs.ExitNodeAllowLANAccess" (ngModelChange)="edit('exit-node-lan',$event)" [disabled]="busy()||!s.can_exit||!s.can_exit_lan" /></div>
        </ng-container>
        <div class="row" *ngIf="s.show_run_exit"><span>Run as exit node</span><sfng-toggle name="Run as exit node" controlId="connectivity-run-exit" [ngModel]="s.prefs.RunExitNode" (ngModelChange)="edit('run-exit-node',$event)" [disabled]="busy()||!s.can_run_exit" /></div>
        <details class="preference-details"><summary>How preferences apply</summary><p class="hint">Changes save automatically through the same local daemon API as the tray. A changed profile or setting requires reload. Managed preferences stay visible but cannot be edited.</p></details>
        <button id="connectivity-reset" *ngIf="s.show_reset" [disabled]="busy()||!s.can_reset" (click)="ask('reset')">Reset to defaults…</button>
      </app-dashboard-widget>
      <app-dashboard-widget label="Custom DNS resolver" brand="tailscale" *ngIf="view==='DNS resolver'">
        <div class="resolver-primary"><h2>{{resolverProvider()}}</h2><p>{{s.resolver.Applied?'Custom resolver applied':s.resolver.Configured?'Saved resolver is not currently applied':'Using the tailnet DNS configuration'}}</p></div>
        <div class="resolver-state"><span class="badge" [class.good]="dnsAccepted()">Tailnet DNS · {{dnsAccepted()?'Enabled':'Disabled'}}</span>
          <span class="badge" [class.good]="s.resolver.Applied">Custom override · {{s.resolver.Applied?'Applied':s.resolver.Configured?'Saved, not applied':'Not configured'}}</span></div>
        <p class="hint">{{s.resolver.Configured?s.resolver.Reason:'No per-device endpoint is saved. The tailnet DNS preference does not configure a custom provider.'}}</p>
        <details class="resolver-editor" [open]="!s.resolver.Configured"><summary>{{s.resolver.Configured?'Edit DNS resolver':'Configure DNS resolver'}}</summary>
        <label>HTTPS DNS endpoint<input id="connectivity-resolver" [(ngModel)]="endpoint" placeholder="https://dns.controld.com/your-endpoint" (blur)="saveResolver()" (keydown.enter)="$event.preventDefault();saveResolver()" [disabled]="busy()||!s.can_resolver" maxlength="2048"></label>
        <p class="hint">A valid endpoint saves when you leave the field. Saved and applied are separate states; this does not prove provider reachability.</p>
        <button id="connectivity-resolver-disable" [disabled]="busy()||!s.can_resolver||!s.resolver.Configured" (click)="edit('resolver-enabled',false)">Disable custom resolver</button>
        </details>
        <p class="hint" *ngIf="s.resolver.CaptivePortal">Temporary captive-portal handling is active. Your saved provider is retained.</p>
      </app-dashboard-widget>
    </ng-container>
    <section *ngIf="confirming()" class="connectivity-confirm" role="group" aria-label="Confirm network change">
      <h2>{{confirming()==='reset'?'Reset device preferences?':'Disconnect this device?'}}</h2>
      <p>{{confirming()==='reset'?'Reset DNS, route, incoming-connection, unattended and automatic-update preferences. Authentication and keys remain intact.':'Tailnet access will stop until you reconnect.'}}</p>
      <div class="actions"><button id="connectivity-confirm" [disabled]="busy()" (click)="confirm()">Confirm</button><button [disabled]="busy()" (click)="cancelConfirmation()">Cancel</button></div>
    </section>
  </section>`})
export class Connectivity {
  @Output() adminVisibility=new EventEmitter<boolean>();
  deviceSearch='';exitEnabled=false;
  relative=relativeSeen;os=osSymbol;
  presence(online:boolean|null){return online===true?'Online':online===false?'Offline':'Presence unknown'}

  toggleExit(value:boolean){this.exitEnabled=value;if(!value&&this.state()?.prefs.ExitNodeID)void this.edit('exit-node','')}
  @Input() view='Connection';state=signal<ConnectivityState|null>(null);busy=signal(false);error=signal('');notice=signal('');confirming=signal<'reset'|'disconnect'|null>(null);endpoint='';
  constructor(){void this.load()}
  exitNodes(){return this.state()?.peers.filter(peer=>peer.exit)||[]}
  visiblePeers(){const search=this.deviceSearch.trim().toLocaleLowerCase();return (this.state()?[this.state()!.self,...this.state()!.peers.filter(p=>p.id!==this.state()!.self.id)]:[]).filter(peer=>
    !search||[peer.name,peer.owner,...peer.addresses,...peer.tags].some(value=>value?.toLocaleLowerCase().includes(search)))}
  time(value:string|null){return value?new Date(value).toLocaleString():'Not reported in this live snapshot'}
  dnsAccepted(){return this.state()?.preferences.find(pref=>pref.id==='use-dns')?.value===true}
  resolverProvider(){const s=this.state();if(!s?.resolver.Configured)return 'Tailnet DNS';
    try{const host=new URL(s.resolver.Endpoint).hostname;return host==='dns.controld.com'?'Control D':host.endsWith('.nextdns.io')||host==='dns.nextdns.io'?'NextDNS':host}catch{return 'Custom DNS resolver'}}
  async load(){if(this.busy())return;this.busy.set(true);this.error.set('');this.confirming.set(null);
    try{const s=await command<ConnectivityState>('connectivity-read');this.state.set(s);this.adminVisibility.emit(s.show_admin);this.endpoint=s.resolver.Endpoint||''}
    catch(e){this.error.set((e as Error).message);this.state.set(null)}finally{this.busy.set(false)}}
  async edit(preference:string,value:unknown,confirm=false){const s=this.state();if(!s||this.busy())return;this.busy.set(true);this.error.set('');this.notice.set('');
    try{const next=await command<ConnectivityState>('connectivity-edit',{revision:s.revision,preference,value,...(confirm?{confirm:true}:{})});this.state.set(next);this.adminVisibility.emit(next.show_admin);this.endpoint=next.resolver.Endpoint||'';this.notice.set('Saved and read back from the device.')}
    catch(e){this.error.set((e as Error).message);this.state.set(null)}finally{this.busy.set(false)}}
  saveResolver(){if(this.endpoint&&this.endpoint!==this.state()?.resolver.Endpoint)void this.edit('resolver',this.endpoint)}
  ask(action:'reset'|'disconnect'){this.confirming.set(action);requestAnimationFrame(()=>document.getElementById('connectivity-confirm')?.focus())}
  cancelConfirmation(){const action=this.confirming();this.confirming.set(null);requestAnimationFrame(()=>document.getElementById(action==='reset'?'connectivity-reset':'connectivity-toggle')?.focus())}
  async confirm(){const action=this.confirming();if(!action||this.busy()||!this.state())return;
    if(action==='disconnect'){this.confirming.set(null);await this.edit('connected',false,true);return}
    this.busy.set(true);this.error.set('');
    try{const next=await command<ConnectivityState>('connectivity-reset',{revision:this.state()!.revision,confirm:true});this.state.set(next);this.adminVisibility.emit(next.show_admin);this.endpoint=next.resolver.Endpoint||'';this.notice.set('Defaults restored and read back.')}
    catch(e){this.error.set((e as Error).message);this.state.set(null)}finally{this.busy.set(false);this.confirming.set(null)}}
}

@Component({selector:'taild-about',standalone:true,imports:[CommonModule,BrandMark],template:`
  <section id="about-panel">
    <div class="about-identity"><taild-brand-mark brand="tailscale" /><div><h2>TailD</h2><p>Independent TailDNS / Tailscale fork · local network analytics and control</p></div></div>
    <dl class="about-facts"><dt>Release</dt><dd id="about-version">{{data()?.version||'Reading version…'}}</dd><dt>CLI</dt><dd>{{data()?.cli_version||'Unavailable'}}</dd>
      <dt>Inherited core</dt><dd>{{data()?.core||'Unavailable'}}</dd><dt>Licensing</dt><dd>{{data()?.license||'GPL-3.0-only desktop / BSD-3-Clause inherited core'}}</dd></dl>
    <p class="hint">Tailscale and Control D marks identify the inherited product and integration; TailD is not an official or endorsed release of either company.</p><p class="error" role="alert" *ngIf="error()">{{error()}}</p>
    <div class="actions"><button id="about-project" (click)="open('project')">Project</button><button (click)="open('releases')">Releases</button><button (click)="open('licenses')">Licenses & attribution</button></div>
  </section>`})
export class About {
  data=signal<Record<string,string>|null>(null);error=signal('');
  constructor(){void command<Record<string,string>>('connectivity-about').then(data=>this.data.set(data)).catch(()=>this.data.set({version:'Unavailable'}))}
  async open(target:string){try{await command('open-product-link',{target})}catch(e){this.error.set((e as Error).message)}}
}
