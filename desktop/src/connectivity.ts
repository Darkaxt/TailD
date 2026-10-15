// SPDX-License-Identifier: GPL-3.0-only
import {Component,Input,signal} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {command} from './bridge';
import {DashboardWidgetComponent} from './portmaster/panel';
import {SfngToggleSwitchComponent} from './portmaster/toggle';
import {BrandMark} from './brand-mark';

interface Preference {id:string;label:string;value:boolean;visible:boolean;editable:boolean}
interface Peer {id:string;name:string;addresses:string[];online:boolean;exit:boolean}
interface ConnectivityState {revision:string;profile:string;account:string;state:string;device:string;addresses:string[];
  preferences:Preference[];prefs:{WantRunning:boolean;ExitNodeID:string;ExitNodeAllowLANAccess:boolean;RunExitNode:boolean};
  resolver:{Configured:boolean;Endpoint:string;Applied:boolean;CaptivePortal:boolean;Reason:string};
  peers:Peer[];show_peers:boolean;show_exit:boolean;show_run_exit:boolean;show_reset:boolean;
  can_disconnect:boolean;can_exit:boolean;can_exit_lan:boolean;can_run_exit:boolean;can_reset:boolean;can_resolver:boolean}

@Component({selector:'taild-connectivity',standalone:true,imports:[CommonModule,FormsModule,DashboardWidgetComponent,SfngToggleSwitchComponent],template:`
  <section id="connectivity-window" class="connectivity-workspace" [attr.aria-busy]="busy()">
    <div class="connectivity-toolbar"><span class="badge" [class.good]="state()?.state==='Running'">{{state()?.state||(busy()?'Reading device…':'Unavailable')}}</span>
      <button id="connectivity-reload" (click)="load()" [disabled]="busy()">Reload device</button>
      <span class="hint" role="status">{{busy()?'Reading / applying device settings…':notice()}}</span></div>
    <div *ngIf="error()" id="connectivity-error" class="error" role="alert">{{error()}}</div>
    <ng-container *ngIf="state() as s">
      <div class="grid" *ngIf="view==='Connection'">
        <app-dashboard-widget label="This device" brand="tailscale">
          <h2 class="device-name">{{s.device||'Not connected'}}</h2><p>{{s.account||'No active account'}}</p>
          <div class="device-addresses"><code *ngFor="let address of s.addresses">{{address}}</code></div>
          <button id="connectivity-toggle" [disabled]="busy()||!s.profile||!s.can_disconnect" (click)="s.prefs.WantRunning?ask('disconnect'):edit('connected',true)">{{s.prefs.WantRunning?'Disconnect':'Connect'}}</button>
          <p class="hint">Uses your existing Tailscale service and authenticated device. Account sign-in and Taildrop remain available from the tray.</p>
        </app-dashboard-widget>
        <app-dashboard-widget label="Exit node" brand="tailscale" *ngIf="s.show_exit">
          <label>Internet routing<select id="connectivity-exit" [ngModel]="s.prefs.ExitNodeID||''" (ngModelChange)="edit('exit-node',$event)" [disabled]="busy()||!s.can_exit">
            <option value="">Do not use an exit node</option><option *ngFor="let peer of exitNodes()" [value]="peer.id">{{peer.name}}{{peer.online?'':' · offline'}}</option></select></label>
          <div class="row"><span>Allow local network access</span><sfng-toggle name="Allow local network access" controlId="connectivity-exit-lan" [ngModel]="s.prefs.ExitNodeAllowLANAccess" (ngModelChange)="edit('exit-node-lan',$event)" [disabled]="busy()||!s.can_exit||!s.can_exit_lan||!s.prefs.ExitNodeID" /></div>
          <div class="row" *ngIf="s.show_run_exit"><span>Run as exit node</span><sfng-toggle name="Run as exit node" controlId="connectivity-run-exit" [ngModel]="s.prefs.RunExitNode" (ngModelChange)="edit('run-exit-node',$event)" [disabled]="busy()||!s.can_run_exit" /></div>
          <p class="hint">Only the selected route preference changes. Tailnet identity and signing keys are retained.</p>
        </app-dashboard-widget>
        <app-dashboard-widget label="Network devices" brand="tailscale" class="wide" *ngIf="s.show_peers">
          <div class="table-scroll"><table><thead><tr><th>Device</th><th>Tailscale addresses</th><th>Status</th></tr></thead><tbody>
            <tr *ngFor="let peer of s.peers"><td>{{peer.name}}</td><td>{{peer.addresses.join(' · ')}}</td><td><span class="badge" [class.good]="peer.online">{{peer.online?'Online':'Offline'}}</span></td></tr></tbody></table></div>
          <p *ngIf="!s.peers.length" class="hint">No peer devices reported by the local daemon.</p>
        </app-dashboard-widget>
      </div>
      <app-dashboard-widget label="Device preferences" brand="tailscale" *ngIf="view==='Preferences'">
        <ng-container *ngFor="let pref of s.preferences"><div class="row" *ngIf="pref.visible"><div><div class="row-title">{{pref.label}}</div><small class="hint" *ngIf="!pref.editable">Managed by system policy / account</small></div>
          <sfng-toggle [name]="pref.label" [controlId]="'connectivity-'+pref.id" [ngModel]="pref.value" (ngModelChange)="edit(pref.id,$event)" [disabled]="busy()||!pref.editable" /></div></ng-container>
        <p class="hint">Changes save automatically through the same local daemon API as the tray. A changed profile or setting requires reload.</p>
        <button id="connectivity-reset" *ngIf="s.show_reset" [disabled]="busy()||!s.can_reset" (click)="ask('reset')">Reset to defaults…</button>
      </app-dashboard-widget>
      <app-dashboard-widget label="Custom DNS resolver" brand="tailscale" *ngIf="view==='DNS resolver'">
        <div class="resolver-state"><span class="badge" [class.good]="dnsAccepted()">Tailnet DNS · {{dnsAccepted()?'Enabled':'Disabled'}}</span>
          <span class="badge" [class.good]="s.resolver.Applied">Custom override · {{s.resolver.Applied?'Applied':s.resolver.Configured?'Saved, not applied':'Not configured'}}</span></div>
        <p class="hint">{{s.resolver.Configured?s.resolver.Reason:'No per-device endpoint is saved. The tailnet DNS preference does not configure a custom provider.'}}</p>
        <label>HTTPS DNS endpoint<input id="connectivity-resolver" [(ngModel)]="endpoint" placeholder="https://dns.controld.com/your-endpoint" (blur)="saveResolver()" (keydown.enter)="$event.preventDefault();saveResolver()" [disabled]="busy()||!s.can_resolver" maxlength="2048"></label>
        <p class="hint">A valid endpoint saves when you leave the field. Saved and applied are separate states; this does not prove provider reachability.</p>
        <button id="connectivity-resolver-disable" [disabled]="busy()||!s.can_resolver||!s.resolver.Configured" (click)="edit('resolver-enabled',false)">Disable custom resolver</button>
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
  @Input() view='Connection';state=signal<ConnectivityState|null>(null);busy=signal(false);error=signal('');notice=signal('');confirming=signal<'reset'|'disconnect'|null>(null);endpoint='';
  constructor(){void this.load()}
  exitNodes(){return this.state()?.peers.filter(peer=>peer.exit)||[]}
  dnsAccepted(){return this.state()?.preferences.find(pref=>pref.id==='use-dns')?.value===true}
  async load(){if(this.busy())return;this.busy.set(true);this.error.set('');this.confirming.set(null);
    try{const s=await command<ConnectivityState>('connectivity-read');this.state.set(s);this.endpoint=s.resolver.Endpoint||''}
    catch(e){this.error.set((e as Error).message);this.state.set(null)}finally{this.busy.set(false)}}
  async edit(preference:string,value:unknown,confirm=false){const s=this.state();if(!s||this.busy())return;this.busy.set(true);this.error.set('');this.notice.set('');
    try{const next=await command<ConnectivityState>('connectivity-edit',{revision:s.revision,preference,value,...(confirm?{confirm:true}:{})});this.state.set(next);this.endpoint=next.resolver.Endpoint||'';this.notice.set('Saved and read back from the device.')}
    catch(e){this.error.set((e as Error).message);this.state.set(null)}finally{this.busy.set(false)}}
  saveResolver(){if(this.endpoint&&this.endpoint!==this.state()?.resolver.Endpoint)void this.edit('resolver',this.endpoint)}
  ask(action:'reset'|'disconnect'){this.confirming.set(action);requestAnimationFrame(()=>document.getElementById('connectivity-confirm')?.focus())}
  cancelConfirmation(){const action=this.confirming();this.confirming.set(null);requestAnimationFrame(()=>document.getElementById(action==='reset'?'connectivity-reset':'connectivity-toggle')?.focus())}
  async confirm(){const action=this.confirming();if(!action||this.busy()||!this.state())return;
    if(action==='disconnect'){this.confirming.set(null);await this.edit('connected',false,true);return}
    this.busy.set(true);this.error.set('');
    try{const next=await command<ConnectivityState>('connectivity-reset',{revision:this.state()!.revision,confirm:true});this.state.set(next);this.endpoint=next.resolver.Endpoint||'';this.notice.set('Defaults restored and read back.')}
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
