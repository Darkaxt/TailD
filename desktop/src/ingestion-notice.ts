// SPDX-License-Identifier: GPL-3.0-only
import {Component,Input,OnDestroy,signal} from '@angular/core';
import {CommonModule} from '@angular/common';
import {command} from './bridge';
import {State} from './collection';
import {describeIngestion,IngestionCatalog} from './ingestion-state';
import {BrandMark} from './brand-mark';

@Component({selector:'taild-ingestion-notice',standalone:true,imports:[CommonModule,BrandMark],template:`
  <section id="ingestion-notice" class="ingestion-notice" aria-label="History ingestion">
    <div class="ingestion-heading"><span class="ingestion-dot" [class.active]="description().active" aria-hidden="true"></span>
      <strong id="ingestion-status" role="status" aria-live="polite">{{description().title}}</strong>
      <span class="hint">Import activity is not proof of complete coverage.</span></div>
    <div class="ingestion-sources"><div *ngFor="let source of description().sources" [attr.id]="'ingestion-'+source.kind">
      <span class="source-label provider-brand"><taild-brand-mark brand="controld" *ngIf="source.kind==='dns'" />{{source.label}}</span><span class="ingestion-activity">{{source.activity}}</span>
      <small>Latest stored observation: {{source.latest || 'none yet'}}</small>
      <small class="ingestion-gap" *ngIf="source.outsideStoredData">No stored observations overlap the selected period yet; an empty graph does not prove zero activity.</small>
    </div></div>
    <small id="ingestion-observer-error" *ngIf="error()">Status unavailable. Retained graphs and collection settings are unchanged.</small>
  </section>`})
export class IngestionNotice implements OnDestroy {
  observed=signal<State|null>(null);retained=signal<IngestionCatalog|null>(null);error=signal(false);
  @Input() set state(value:State|null){if(value)this.observed.set(value)}
  @Input() set catalog(value:IngestionCatalog|null){if(value)this.retained.set(value)}
  @Input() start='';@Input() end='';
  @Input() primary:'traffic'|'dns'='traffic';
  private disposed=false;private reading=false;private timer?:number;
  private visible=()=>{if(!document.hidden)void this.observe()};
  constructor(){document.addEventListener('visibilitychange',this.visible);void this.observe();this.schedule()}
  description(){return describeIngestion(this.observed(),this.retained(),this.start,this.end,this.primary)}
  private schedule(){if(this.disposed)return;this.timer=window.setTimeout(async()=>{
    await this.observe();this.schedule();},5000)}
  private async observe(){
    // Diagnostic cadence only. Never start acquisition, modify scope or refresh
    // facts/revisions; a pending request completes naturally with no deadline.
    if(this.disposed||document.hidden||this.reading)return;this.reading=true;
    try{
      const state=await command<State>('state');if(this.disposed)return;this.observed.set(state);
      const catalog=await command<IngestionCatalog>('view-catalog');if(this.disposed)return;
      this.retained.set(catalog);this.error.set(false);
    }catch{if(!this.disposed)this.error.set(true)}finally{this.reading=false}
  }
  ngOnDestroy(){this.disposed=true;window.clearTimeout(this.timer);document.removeEventListener('visibilitychange',this.visible)}
}
