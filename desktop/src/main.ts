// SPDX-License-Identifier: GPL-3.0-only
// Portmaster-derived dashboard / explorer composition; source identities in NOTICE.md.
import {bootstrapApplication} from '@angular/platform-browser';
import {Component,computed,signal,provideZonelessChangeDetection} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {command} from './bridge';
import {IngestionNotice} from './ingestion-notice';
import {Collection,State} from './collection';
import {DashboardWidgetComponent} from './portmaster/panel';
import {Bin,Consumer,CircularBarChartComponent,SfngNetqueryLineChartComponent,bytes,exact} from './portmaster/charts';
import {Evidence} from './evidence';
import {applicationName} from './application-label';
import {WorldMapComponent,GeographyRow} from './portmaster/world-map';
import {DEFAULT_TIME_RANGE,presetBounds} from './time-range';
import {mergeProgress,BatchProgress} from './progressive-batch';

type Kind='traffic'|'dns'|'correlations';
type Page='Overview'|'Applications'|'Activity'|'Control D'|'Sources & health'|'Settings';
type Fact=Record<string,any>;
interface Query {kind:string;view:string;start:string;end:string;scope:Record<string,string>;
  where?:Predicate;search?:string;group_by?:string[];order_by?:{field:string;direction:string}[];
  limit?:number;cursor?:string;bin_seconds?:number;anchor_id?:string}
interface Predicate {field?:string;op?:string;value?:unknown;all?:Predicate[];any?:Predicate[]}
interface Result {revision:number;value_state:string;coverage:Fact;data:Fact;start:string;end:string;scope:Record<string,string>}
interface Batch {revision:number;aggregation_version:string;correlation_version:string;results:Result[]}
interface Catalog {sources:{id:string;kind:string;scope:string;endpoint?:string}[];
  intervals:Record<string,{start:string|null;end:string|null}>;health:Fact;nodes:{host_scope:string;node_id:string}[];nodes_truncated:boolean}
interface Saved {name:string;query:Query}
const numeric=new Set(['timestamp','destination_port','protocol_raw','inbound_bytes','outbound_bytes','total_bytes']);
const fields:Record<Kind,string[]>={
  traffic:['application','application_path','destination_ip','destination_port','protocol_raw','total_bytes','inbound_bytes','outbound_bytes','source','correlation_state','context_state','destination_country','destination_asn','question','type','endpoint','profile','action','outcome','reason','client','id','timestamp'],
  correlations:['application','application_path','destination_ip','destination_port','protocol_raw','total_bytes','source','correlation_state','context_state','question','endpoint','profile','reason','id','timestamp'],
  dns:['question','type','endpoint','profile','client','action','outcome','reason','reason_value','protocol','provider_country','provider_asn','source','id','timestamp']};

@Component({selector:'taild-app',standalone:true,
  imports:[CommonModule,FormsModule,Collection,DashboardWidgetComponent,CircularBarChartComponent,SfngNetqueryLineChartComponent,Evidence,IngestionNotice,WorldMapComponent],
  template:`
  <button class="skip-link" (click)="skipContent()">Skip to analytics content</button>
  <div class="screen-reader-progress" role="status" aria-live="polite" aria-atomic="true">{{busy()?(pendingBatch()?'Some analytics panels are ready. Reading the remaining panels.':'Loading analytics…'):ready()?'Analytics view ready.':''}}</div>
  <nav class="rail" aria-label="TailD navigation"><span class="brand" title="TailD · independent fork">TD</span>
    <button *ngFor="let item of pages;let i=index" [id]="'nav-'+i" class="nav-link" [class.active]="page()===item" [disabled]="!catalog()"
      [attr.aria-label]="item" [attr.aria-current]="page()===item?'page':null" [title]="item" (click)="navigate(item)">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path [attr.d]="icons[i]" fill="none" stroke="currentColor" stroke-width="1.6" /></svg></button>
    <span class="rail-bottom" title="Read-only analytics">READ</span></nav>
  <main id="analytics-main" tabindex="-1" class="analytics-shell" [attr.aria-busy]="busy()" [attr.data-revision]="displayBatch()?.revision" [attr.data-ready]="ready()">
    <header class="page-heading"><div><div class="eyebrow">TailD / Network analytics</div><h1>{{page()}}</h1>
      <p>{{page()==='Applications'&&application()!==undefined?appName(application()):'Observed facts. Honest gaps. Your network stays unchanged.'}}</p></div>
      <div class="heading-status"><span class="badge" [class.good]="runtime()?.state==='collecting'">{{runtime()?.state||'Connecting'}}</span>
      <span class="revision" *ngIf="displayBatch() as b">Revision {{b.revision}}{{pendingBatch()?' · loading panels':''}}</span></div></header>
    <taild-ingestion-notice *ngIf="page()!=='Settings'&&page()!=='Overview'" [state]="runtime()" [catalog]="catalog()" [start]="start" [end]="end" />
    <fieldset class="shared-scope" aria-label="Shared analytics scope" [disabled]="busy()" *ngIf="catalog() as c">
      <label>Host scope<select id="scope-host" [(ngModel)]="host" (change)="hostChanged()"><option value="">All recorded hosts</option>
        <option *ngFor="let value of hosts()" [value]="value">{{value}}</option></select></label>
      <label>Observed node · traffic only<select id="scope-device" [(ngModel)]="device" (change)="scopeChanged()"><option value="">All / historical binding unknown</option>
        <option *ngFor="let value of nodes()" [value]="value">{{value}}</option></select></label>
      <label>Control D account<select id="scope-account" [(ngModel)]="account" (change)="accountChanged()"><option value="">All recorded accounts</option>
        <option *ngFor="let value of accounts()" [value]="value">{{value}}</option></select></label>
      <label>Endpoint · not host attribution<select id="scope-endpoint" [(ngModel)]="endpoint" (change)="scopeChanged()"><option value="">All recorded endpoints</option>
        <option *ngFor="let value of endpoints()" [value]="value">{{value}}</option></select></label>
      <label>Time range<select id="time-range" [(ngModel)]="range" (change)="timeChanged()">
        <option value="week">Last 7 days</option>
        <option value="recent">Recent · 15 minutes</option><option value="hour">Last hour</option><option value="today">Today</option>
        <option value="custom">Explicit UTC range</option></select></label>
      <button id="view-refresh" [disabled]="busy()" (click)="refresh(true)">Refresh view</button>
      <div class="utc-range"><label>From · UTC<input id="utc-start" [(ngModel)]="start" (change)="customTime()" aria-label="Start UTC timestamp"></label>
        <label>Until · UTC, exclusive<input id="utc-end" [(ngModel)]="end" (change)="customTime()" aria-label="End UTC timestamp"></label>
        <span class="hint">{{localTime(start)}} → {{localTime(end)}} · {{timezone}}</span>
        <button id="available-history" (click)="availableHistory()" [disabled]="busy()">Latest retained hour</button></div>
    </fieldset>
    <div *ngIf="error()" id="analytics-error" class="error" role="alert">{{error()}}</div>
    <div class="filter-tags" [attr.inert]="busy()?'':null" *ngIf="application()!==undefined || predicates.length || search">
      <span class="filter-pill" *ngIf="application()!==undefined">Application: {{appName(application())}}<button aria-label="Remove application scope" (click)="clearApplication()">×</button></span>
      <span class="filter-pill" *ngFor="let filter of predicates;let i=index">{{predicateLabel(filter)}}<button [attr.aria-label]="'Remove filter '+(i+1)" (click)="removeFilter(i)">×</button></span>
      <span class="filter-pill" *ngIf="search">Search: {{search}}<button aria-label="Remove search" (click)="clearSearch()">×</button></span>
    </div>
    <div class="view-meta" *ngIf="batch() as b"><span id="coverage-state" *ngIf="trafficResult() as t" class="badge" [class.warn]="t.value_state!=='observed'">{{t.value_state}} traffic</span>
      <span *ngIf="dnsResult() as d" class="badge" [class.warn]="d.value_state!=='observed'">{{d.value_state}} DNS</span>
      <span class="hint">{{b.aggregation_version}} · no socket/PID bytes or firewall verdicts</span>
      <span class="hint" *ngIf="application()!==undefined || predicates.length || device">DNS totals use independent endpoint scope when node/traffic/application filters cannot apply.</span>
      <span class="hint" *ngIf="catalog()?.nodes_truncated">Observed-node list is truncated; narrow the host scope.</span></div>
    <div class="loading-overlay" *ngIf="busy()&&!pendingBatch()" role="status" aria-live="polite" aria-atomic="true" id="view-loading">
      <div class="loading-dialog"><div class="loading-dots" aria-hidden="true"><span></span><span></span><span></span></div>
        <strong>{{batch()?'Refreshing view':'Loading analytics'}}</strong><span>Reading local history</span>
        <small>{{batch()?'Your previous revision is kept until the new view is ready.':'Preparing the selected view.'}}</small></div></div>
    <div class="progress-notice" *ngIf="busy()&&pendingBatch()" role="status" aria-live="polite" id="view-progress">
      <span class="progress-pulse" aria-hidden="true"></span><strong>Loading remaining panels</strong>
      <span>{{dnsSummary()?'Control D decisions ready.':'Reading Control D decisions.'}} {{summary()?'Traffic summary ready.':'Reading traffic aggregates.'}}</span>
      <small>One consistent revision · drill-down available when this view finishes</small></div>
    <div class="analytics-results" [attr.inert]="busy()?'':null" [attr.data-progress]="!!pendingBatch()">

    <ng-container *ngIf="page()==='Overview' || (page()==='Applications'&&application()!==undefined)">
      <div class="dashboard-grid" [class.application-dashboard]="application()!==undefined" *ngIf="(summary() || pendingSummary) as s">
        <app-dashboard-widget label="Activity in the selected period" id="dashboard-stats" [attr.data-pending]="!summary()">
          <div class="mini-stats-list"><button class="mini-stat" id="received-card" (click)="explore('traffic')"><label>Received</label><span>{{summary()?format(s.data.inbound_bytes):'Loading…'}}</span><small>{{summary()?s.data.inbound_bytes+' bytes':'Traffic history'}}</small></button>
            <button class="mini-stat" id="sent-card" (click)="explore('traffic')"><label>Sent</label><span>{{summary()?format(s.data.outbound_bytes):'Loading…'}}</span><small>{{summary()?s.data.outbound_bytes+' bytes':'Traffic history'}}</small></button>
            <button class="mini-stat" id="applications-card" (click)="navigate('Applications')"><label>Observed applications</label><span>{{s.application_activity.known_distinct}}</span><small>{{s.application_activity.unknown_buckets}} unknown buckets</small></button>
            <button class="mini-stat" id="dns-card" (click)="explore('dns')"><label>DNS decisions</label><span>{{dnsSummary()?.dns_activity.events??'Unavailable'}}</span><small>Independent endpoint scope</small></button>
            <button class="mini-stat" id="buckets-card" (click)="explore('traffic')"><label>Traffic buckets</label><span>{{s.application_activity.bucket_count}}</span><small>Not live connections</small></button>
            <button class="mini-stat" id="questions-card" (click)="explore('dns','question')"><label>Question groups</label><span>{{dnsSummary()?.dns_questions.distinct??'Unavailable'}}</span><small>Unknown names retained</small></button></div>
        </app-dashboard-widget>
        <app-dashboard-widget label="Collection & source context" id="dashboard-collection" *ngIf="page()==='Overview'">
          <div class="source-priority"><span class="source-label">Control D</span><span class="hint">DNS decisions & policy</span></div>
          <div class="dashboard-source-actions"><button id="dashboard-provider" (click)="navigate('Control D')">Control D details <span aria-hidden="true">→</span></button>
            <button id="dashboard-health" (click)="navigate('Sources & health')">Source health <span aria-hidden="true">→</span></button>
            <button id="dashboard-settings" (click)="navigate('Settings')">Manage collection <span aria-hidden="true">→</span></button></div>
          <taild-ingestion-notice primary="dns" [state]="runtime()" [catalog]="catalog()" [start]="start" [end]="end" />
          <p class="hint">READ only. GlassWire supplies application bytes; Control D supplies endpoint DNS decisions. Neither proves complete coverage.</p>
        </app-dashboard-widget>
        <app-dashboard-widget label="DNS activity · canonical decisions" id="dashboard-dns-trend" [class.panel-pending]="!displayBatch()?.results?.[7]">
          <p class="hint">Independent account/endpoint scope · select a bin to inspect its decisions.</p>
          <sfng-netquery-line-chart metric="decisions" [data]="dnsBins()" (select)="dnsBinScope($event)" />
        </app-dashboard-widget>
        <app-dashboard-widget label="Bandwidth history · observed samples" class="half chart-panel" id="dashboard-bandwidth" [class.panel-pending]="!displayBatch()?.results?.[2]">
          <sfng-netquery-line-chart [data]="bins()" (select)="binScope($event)" />
        </app-dashboard-widget>
        <app-dashboard-widget [label]="application()===undefined?'Top applications · received / sent':'Top destinations · application scoped'" class="half" id="dashboard-consumers" [class.panel-pending]="!displayBatch()?.results?.[3]">
          <sfng-netquery-circular-bar-chart [data]="application()===undefined?consumers():destinations()" (select)="selectConsumer($event)" />
        </app-dashboard-widget>
        <app-dashboard-widget label="Correlation evidence · not attribution" class="half" id="dashboard-correlations" [class.panel-pending]="!summary()">
          <div class="partition" aria-label="Correlation bytes partition"><ng-container *ngFor="let item of correlation()"><button *ngIf="item.weight>0" [style.flex-grow]="item.weight" [title]="item.name+': '+item.bytes+' bytes'"
              [attr.aria-label]="item.name+': '+item.bytes+' bytes'" (click)="correlationScope(item.name)">{{item.weight>15?item.name:''}}</button></ng-container></div>
          <div class="rank-table"><button *ngFor="let item of correlation()" (click)="correlationScope(item.name)"><span>{{item.name}}</span><span>{{format(item.bytes)}}</span><small>{{item.count}} buckets</small></button></div>
          <p class="hint">A unique temporal candidate is an inference. Cache, TTL and process-to-domain origin are unproven.</p>
        </app-dashboard-widget>
        <app-dashboard-widget label="DNS outcomes · Control D decisions" class="half" id="dashboard-outcomes" [class.panel-pending]="!dnsSummary()">
          <p class="hint">Observed decision categories for the selected endpoint.</p>
          <div class="partition" aria-label="DNS outcome distribution"><ng-container *ngFor="let item of outcomes()"><button *ngIf="item.count>0" [attr.data-outcome]="item.name" [style.flex-grow]="item.count" (click)="outcomeScope(item.name)" [attr.aria-label]="outcomeLabel(item.name)+': '+item.count+' decisions'">{{outcomeLabel(item.name)}}</button></ng-container></div>
          <div class="rank-table"><ng-container *ngFor="let item of outcomes()"><button *ngIf="item.count>0" (click)="outcomeScope(item.name)"><span>{{outcomeLabel(item.name)}}</span><span>{{item.count}}</span></button></ng-container></div>
          <p class="hint" *ngIf="!dnsSummary()?.dns_activity.events">No DNS decisions observed in this scope.</p>
          <p class="hint" *ngIf="dnsSummary()?.dns_outcomes as outcomes">{{outcomes.classified_denominator}} classified successful decisions · {{outcomes.excluded_failed}} failed · {{outcomes.excluded_unknown}} unknown. Unknown does not mean bypassed.</p>
        </app-dashboard-widget>
        <app-dashboard-widget label="DNS questions · selected endpoint" class="half" id="dashboard-questions" [class.panel-pending]="!dnsSummary()">
          <div class="rank-table"><button *ngFor="let item of questions().slice(0,12)" (click)="questionScope(item.value)"><span>{{item.value||'Unknown question'}}</span><span>{{item.events}} decisions</span></button></div>
          <p *ngIf="!questions().length" class="hint">No provider decisions observed in this scope.</p>
          <p class="hint" *ngIf="application()!==undefined">Independent endpoint DNS scope, not all queries from this application. Candidate questions are in its activity evidence.</p>
          <div class="rank-table" *ngIf="application()!==undefined"><h3>Application candidate questions · inferred</h3><button *ngFor="let item of s.candidate_domains.inferred" (click)="candidateQuestionScope(item.question)"><span>{{item.question}}</span><span>{{format(item.total_bytes)}}</span></button></div>
        </app-dashboard-widget>
        <app-dashboard-widget label="Destinations · exact bucket bytes" class="half" id="dashboard-destinations" *ngIf="application()===undefined" [class.panel-pending]="!summary()">
          <div class="rank-table"><button *ngFor="let item of destinations().slice(0,12)" (click)="destinationScope(item.value)"><span>{{item.value||'Unknown destination'}}</span><span>{{format(item.total_bytes)}}</span></button></div>
        </app-dashboard-widget>
        <app-dashboard-widget [label]="geographyMode()==='dns'?'Answer countries / ASN · DNS decisions':'Answer countries / ASN · inferred traffic'" class="half" id="dashboard-countries" [class.panel-pending]="!geographyReady()">
          <label class="geography-selector">Geography metric<select id="geography-mode" [ngModel]="geographyMode()" (ngModelChange)="geographyMode.set($event)"><option value="dns">Control D DNS decisions</option><option value="traffic">Inferred traffic bytes</option></select></label>
          <p class="hint">{{geographyMode()==='dns'?'Independent endpoint scope · provider-reported answer geography, not traffic bytes.':'Unique temporal candidates · inferred bytes, not measured routes.'}} Highlight a country to locate it on the map.</p>
          <div class="country-tiles"><button *ngFor="let item of geographyCountries()" class="country-tile" [attr.data-country]="item.value||'unknown'"
              (mouseenter)="highlightedCountry.set(item.value)" (mouseleave)="highlightedCountry.set(null)"
              (focus)="highlightedCountry.set(item.value)" (blur)="highlightedCountry.set(null)"
              [title]="countryName(item.value)+': '+geographyValue(item)" (click)="selectGeography('country',item.value)">
              <span class="country-code" aria-hidden="true">{{item.value||'?'}}</span><span class="country-name">{{countryName(item.value)}}</span><span>{{geographyValue(item)}}</span></button></div>
          <details class="geography-data"><summary>Exact country / ASN data</summary><div class="table-scroll"><table><caption>Control D answer metadata; not measured routes or device location</caption><thead><tr><th>Country</th><th>{{geographyMode()==='dns'?'DNS decisions':'Inferred bytes'}}</th></tr></thead>
            <tbody><tr *ngFor="let item of geographyCountries()"><td><button class="identity-link" (click)="selectGeography('country',item.value)">{{item.value||'Unknown'}}</button></td><td>{{geographyValue(item)}}</td></tr></tbody></table>
            <table><thead><tr><th>Answer ASN</th><th>{{geographyMode()==='dns'?'DNS decisions':'Inferred bytes'}}</th></tr></thead><tbody><tr *ngFor="let item of geographyAsns()"><td><button class="identity-link" (click)="selectGeography('asn',item.value)">{{item.value||'Unknown'}}</button></td><td>{{geographyValue(item)}}</td></tr></tbody></table></div></details>
        </app-dashboard-widget>
        <app-dashboard-widget [label]="geographyMode()==='dns'?'Answer-country map · DNS decisions':'Answer-country map · inferred traffic'" class="half" id="dashboard-map" [class.panel-pending]="!geographyReady()">
          <taild-world-map *ngIf="geographyReady()" [metric]="geographyMode()==='dns'?'decisions':'traffic'" [data]="geographyCountries()" [highlightedCountry]="highlightedCountry()" (selectCountry)="selectGeography('country',$event)" />
        </app-dashboard-widget>
      </div>
    </ng-container>

    <app-dashboard-widget label="Applications · executable identity, not running processes" *ngIf="page()==='Applications'&&application()===undefined">
      <label class="search-input">Search identities<input id="application-search" [(ngModel)]="search" (keydown.enter)="scopeChanged()" placeholder="Executable path…"></label>
      <div class="table-scroll"><table id="application-table"><thead><tr><th>Application identity</th><th>Received</th><th>Sent</th><th>Last observed UTC</th><th>Candidate coverage</th></tr></thead><tbody>
        <tr *ngFor="let row of applications()"><td><button class="identity-link" [title]="row.keys.application_path||'Unknown executable'" (click)="openApplication(row.keys.application)">{{processName(row.keys.application_path)}}</button><small class="identity-id">{{row.keys.application_path||row.keys.application||'Unknown identity'}}</small></td>
          <td [title]="row.inbound_bytes+' bytes'">{{format(row.inbound_bytes)}}</td><td [title]="row.outbound_bytes+' bytes'">{{format(row.outbound_bytes)}}</td><td>{{row.last_observed_utc}}</td>
          <td>{{row.correlation_counts['unique-candidate']}} unique · {{row.correlation_counts.ambiguous}} ambiguous · {{row.count}} buckets</td></tr>
        <tr *ngIf="!applications().length"><td colspan="5">No application facts observed. Check the selected interval and source coverage.</td></tr></tbody></table></div>
    </app-dashboard-widget>
    <div class="actions" *ngIf="page()==='Applications'&&application()!==undefined"><button (click)="clearApplication()">All applications</button><button class="primary" (click)="explore('traffic')">Inspect application activity</button></div>

    <section *ngIf="page()==='Activity'" id="activity-explorer">
      <div class="explorer-tools"><div class="tabs" role="tablist" aria-label="Fact modes"><button *ngFor="let item of kinds" [id]="'mode-'+item" role="tab" [attr.aria-selected]="kind===item" (click)="setKind(item)">{{item}}</button></div>
        <label class="search-input">Search<input id="activity-search" [(ngModel)]="search" (keydown.enter)="scopeChanged()" placeholder="Literal text; Enter to apply"></label>
        <label>Group<select id="group-by" [(ngModel)]="group" (change)="scopeChanged()"><option value="">Facts</option><option *ngFor="let item of groupFields()" [value]="item">{{item}}</option></select></label>
        <label>Sort<select id="order-by" [(ngModel)]="order" (change)="scopeChanged()"><option value="timestamp:desc">Newest</option><option value="timestamp:asc">Oldest</option><option *ngIf="kind!=='dns'" value="total_bytes:desc">Most bytes</option><option value="id:asc">Stable identity</option></select></label></div>
      <form class="filter-builder" (ngSubmit)="addFilter()"><label>Field<select id="filter-field" [(ngModel)]="field" name="field"><option *ngFor="let item of filterFields()" [value]="item">{{item}}</option></select></label>
        <label>Operator<select id="filter-op" [(ngModel)]="operator" name="operator"><option *ngFor="let item of operators()" [value]="item">{{item}}</option></select></label>
        <label>Value<input id="filter-value" [(ngModel)]="filterValue" name="value" placeholder="Literal value; null means unknown"></label>
        <label>Combine<select id="filter-combine" [(ngModel)]="combine" name="combine"><option value="all">Match all (AND)</option><option value="any">Match any (OR)</option></select></label>
        <button id="add-filter" type="submit" [disabled]="busy()">Add filter</button></form>
      <app-dashboard-widget label="Scoped traffic history" *ngIf="kind!=='dns'"><sfng-netquery-line-chart [data]="bins()" (select)="binScope($event)" /></app-dashboard-widget>
      <app-dashboard-widget label="Activity · observed facts and candidate evidence">
        <div class="explorer-meta"><span id="fact-count">{{group?groups().length:factsResult()?.data?.total_count}} {{group?'groups':'facts'}}</span><span>Revision {{batch()?.revision}}</span>
          <button id="export-json" [disabled]="busy()||!factsResult()" (click)="exportFacts('json')">Export JSON evidence…</button>
          <button id="export-csv" [disabled]="busy()||!factsResult()" (click)="exportFacts('csv')">Export CSV…</button></div>
        <p class="hint">Exports include the whole filtered scope, not just this page (maximum 10,000 facts). Destination selection is explicit; files are private and never overwritten.</p>
        <p id="export-status" role="status" *ngIf="notice()">{{notice()}}</p>
        <div *ngIf="group" class="table-scroll"><table><thead><tr><th>{{group}}</th><th>Facts</th><th>Received</th><th>Sent</th><th>Drill down</th></tr></thead><tbody><tr *ngFor="let row of groups()">
          <td>{{row.keys[group]??'Unknown'}}</td><td>{{row.count}}</td><td>{{kind==='dns'?'Not applicable':format(row.inbound_bytes)}}</td><td>{{kind==='dns'?'Not applicable':format(row.outbound_bytes)}}</td>
          <td><button (click)="groupScope(row.keys[group])">Inspect facts</button></td></tr></tbody></table></div>
        <div id="fact-rows" [hidden]="!!group">
          <div class="fact-header"><span>{{kind==='dns'?'Question / endpoint':'Application / destination'}}</span><span>Source / evidence</span><span>UTC observation</span><span>{{kind==='dns'?'Outcome':'Observed data'}}</span></div>
          <details class="fact-entry" *ngFor="let row of rows();trackBy:trackRow" [attr.data-fact-id]="row.id" [open]="selected()===row.id" (toggle)="rowToggled(row,$event)">
            <summary [attr.id]="'fact-'+row.id" class="fact-row"><span class="fact-identity"><strong [title]="kind==='dns'?row.question:row.application_path">{{kind==='dns'?row.question:processName(row.application_path)}}</strong>
                <small>{{kind==='dns'?row.endpoint:(row.destination_ip||'Unknown address')+(row.destination_port?':'+row.destination_port:'')}}</small></span>
              <span><span class="source-label">{{kind==='dns'?'Control D':'GlassWire'}}</span><small class="candidate-badge">{{row.correlation_state||row.reason||'Provider event'}}</small></span>
              <span>{{utc(row.timestamp)}}<small>{{row.context_state||'Endpoint scope, not physical-host proof'}}</small></span>
              <span>{{kind==='dns'?(row.outcome||'Unknown'):format(row.total_bytes)}}<small>{{kind==='dns'?'Raw action: '+row.action:row.total_bytes+' bytes'}}</small></span></summary>
            <taild-evidence *ngIf="selected()===row.id" [data]="row" /><p class="hint">{{kind==='dns'?'Policy snapshots are point observations, not proof of historical rule causality.':'DNS candidates are inferences. PID, socket lifetime and encryption verdict: unavailable.'}}</p>
          </details>
          <p class="empty-state" *ngIf="!rows().length">No matching observed facts. An empty result is not proof of complete coverage.</p>
          <div class="pagination"><button id="previous-page" [disabled]="busy()||pageIndex===0" (click)="previousPage()">‹ Previous</button><span class="page active-page">Page {{pageIndex+1}}</span>
            <button id="next-page" [disabled]="busy()||!factsResult()?.data?.next_cursor" (click)="nextPage()">Next ›</button></div>
        </div>
      </app-dashboard-widget>
      <div class="saved-queries"><label>Saved local query name<input id="saved-name" maxlength="80" [(ngModel)]="savedName"></label><button id="save-query" [disabled]="busy()||!savedName.trim()" (click)="saveQuery()">Save query</button>
        <label>Reopen saved scope<select id="saved-select" [(ngModel)]="savedSelection"><option value="">Choose…</option><option *ngFor="let item of saved()" [value]="item.name">{{item.name}}</option></select></label>
        <button id="open-query" [disabled]="busy()||!savedSelection" (click)="openSaved()">Open</button><button [disabled]="busy()||!savedSelection" (click)="removeSaved()">Remove</button></div>
    </section>

    <section *ngIf="page()==='Control D'" class="grid">
      <app-dashboard-widget label="Endpoint / account associations" class="wide"><div class="table-scroll"><table><thead><tr><th>Source</th><th>Account scope</th><th>Endpoint</th><th>Association evidence</th></tr></thead><tbody>
        <tr *ngFor="let item of providerSources()"><td>{{item.id}}</td><td>{{item.scope}}</td><td>{{item.endpoint||'Unknown'}}</td><td>Recorded source; endpoint does not prove a physical host</td></tr></tbody></table></div></app-dashboard-widget>
      <app-dashboard-widget label="Policy history · captured READ snapshots" class="wide">
        <p class="hint">Each snapshot is current only at its capture. No provider policy writes; unavailable categories stay visible.</p>
        <p class="hint" *ngIf="batch()?.results?.[6]?.data?.next_cursor">More than 100 snapshots match. Narrow the UTC range to inspect older captures.</p>
        <details *ngFor="let policy of policies()" class="policy-snapshot" [open]="policy===policies()[0]"><summary>{{utc(policy.timestamp)}} · endpoint {{policy.endpoint}} · profile {{policy.profile}}</summary>
          <div class="table-scroll"><table><thead><tr><th>Resource</th><th>Capability / state</th><th>Read contract</th><th>Details</th></tr></thead><tbody>
            <tr *ngFor="let item of resourceEntries(policy.resources)"><td>{{item.name}}</td><td><span class="badge" [class.warn]="item.value.state!=='available'">{{item.value.state||'Unavailable'}}</span></td>
              <td>{{item.value.route||item.value.capability?.route||item.value.source||'Recorded provider READ'}}</td><td><details><summary>Inspect {{item.name}}</summary><taild-evidence [data]="item.value" /></details></td></tr></tbody></table></div>
          <taild-evidence [data]="policyIdentity(policy)" /></details>
        <p *ngIf="!policies().length" class="empty-state">No policy snapshot in this UTC scope. Enable an explicit Control D binding and READ collection in Settings, or select retained history.</p>
      </app-dashboard-widget>
    </section>
    <section *ngIf="page()==='Sources & health'" class="grid">
      <app-dashboard-widget label="Live runtime" class="wide"><div class="status-table" *ngFor="let item of runtimeSources()"><span>{{item.name}}</span><span class="badge" [class.warn]="item.value.state!=='collecting'">{{item.value.state}}</span><taild-evidence [data]="item.value" /></div></app-dashboard-widget>
      <app-dashboard-widget label="History coverage & lag" class="wide"><details *ngFor="let source of summary()?.source_health.sources" class="policy-snapshot"><summary>{{source.kind}} · {{source.id}} · complete through {{source.complete_through||'Unknown'}}</summary><taild-evidence [data]="source" /></details></app-dashboard-widget>
      <app-dashboard-widget label="Storage & privacy" class="wide"><taild-evidence [data]="catalog()?.health||null" /></app-dashboard-widget>
    </section>
    <section *ngIf="page()==='Settings'">
      <taild-collection />
      <app-dashboard-widget label="Retention & private history controls">
        <div class="privacy-controls"><label>Detailed / summary retention (days)<input id="retention-days" type="number" min="1" max="3650" [(ngModel)]="retentionDays" (change)="retentionChanged()"></label>
          <button (click)="cleanupHistory()" [disabled]="busy()">Apply retention now</button><span>{{format(catalog()?.health?.storage_bytes)}} · plaintext SQLite protected by Windows ACLs</span></div>
        <details><summary>Delete selected history · cannot be undone</summary><p>Delete only TailD facts in the shared UTC range. Source data is unchanged. Replay suppression prevents catch-up from restoring deleted facts.</p>
          <p *ngIf="application()!==undefined">Application deletion targets every recorded identity using the displayed executable path in this interval.</p>
          <label>Fact source<select id="delete-kind" [(ngModel)]="deleteKind"><option value="traffic">Traffic</option><option value="dns">DNS</option><option value="context">Context</option><option value="policy">Policy</option></select></label>
          <label><input id="confirm-delete" type="checkbox" style="width:auto" [(ngModel)]="confirmDelete"> I confirm permanent deletion of this selected interval.</label>
          <button id="delete-history" [disabled]="busy()||!confirmDelete" (click)="deleteHistory()">Delete TailD history</button></details>
          <p id="history-status" role="status" *ngIf="notice()">{{notice()}}</p>
      </app-dashboard-widget>
    </section>
    </div><footer><span>TailD · independent TailDNS fork · local READ analytics</span><span>Queries and exports preserve UTC scope, revision and unknowns.</span></footer>
  </main>`})
class App {
  pages:Page[]=['Overview','Applications','Activity','Control D','Sources & health','Settings'];
  icons=['M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z','M3 7h18v14H3zM7 7V3h10v4M3 12h18',
    'M2 12h5l3-8 4 16 3-8h5','M4 4h16v16H4zM8 9h8M8 15h8','M3 4h18v16H3zM7 16v-4M12 16V8M17 16v-6',
    'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2'];
  kinds:Kind[]=['traffic','dns','correlations'];page=signal<Page>('Overview');runtime=signal<State|null>(null);
  catalog=signal<Catalog|null>(null);batch=signal<Batch|null>(null);busy=signal(false);error=signal('');notice=signal('');ready=signal(false);
  pendingBatch=signal<Batch|null>(null);displayBatch=computed(()=>this.pendingBatch()||this.batch());
  pendingSummary={data:{inbound_bytes:null,outbound_bytes:null},application_activity:{known_distinct:'Loading…',unknown_buckets:'Pending',bucket_count:'Loading…'},
    candidate_domains:{inferred:[]},geography_asn:{countries:[],asns:[]}};
  application=signal<string|null|undefined>(undefined);applicationLabel=signal('');selected=signal('');saved=signal<Saved[]>([]);
  host='';device='';account='';endpoint='';range=DEFAULT_TIME_RANGE;start='';end='';timezone=Intl.DateTimeFormat().resolvedOptions().timeZone;
  kind:Kind='traffic';search='';predicates:Predicate[]=[];combine:'all'|'any'='all';field='application_path';operator='eq';filterValue='';
  group='';order='timestamp:desc';pageIndex=0;cursors:(string|undefined)[]=[undefined];savedName='';savedSelection='';retentionDays=7;deleteKind='traffic';confirmDelete=false;
  private lastQuery:Query|null=null;private loadingGeneration=0;private queuedNavigation=false;
  highlightedCountry=signal<string|null>(null);private countryNames=new Intl.DisplayNames(['en'],{type:'region'});
  geographyMode=signal<'dns'|'traffic'>('dns');
  geographyReady=computed(()=>!!(this.geographyMode()==='dns'?this.dnsSummary():this.summary()));
  geographyCountries=computed<GeographyRow[]>(()=>this.geographyMode()==='dns'?this.dnsSummary()?.geography_asn.provider_decisions.country||[]:this.summary()?.geography_asn.countries||[]);
  geographyAsns=computed<Fact[]>(()=>this.geographyMode()==='dns'?this.dnsSummary()?.geography_asn.provider_decisions.asn||[]:this.summary()?.geography_asn.asns||[]);
  geographyValue(item:Fact){return this.geographyMode()==='dns'?item.events+' decisions':this.format(item.total_bytes)}
  outcomeLabel(name:string){return ({allow:'Bypassed',block:'Blocked',redirect:'Redirected',failed:'Request failed',other:'Other',unknown:'Unknown'} as Record<string,string>)[name]||name}
  countryName(value:string|null){return value&&/^[A-Z]{2}$/.test(value)?this.countryNames.of(value)||value:value||'Unknown geography'}
  format=bytes;hosts=computed(()=>[...new Set((this.catalog()?.sources||[]).filter(s=>s.kind==='traffic').map(s=>s.scope))]);
  accounts=computed(()=>[...new Set(this.providerSources().map(s=>s.scope))]);
  endpoints(){return [...new Set(this.providerSources().filter(s=>!this.account||s.scope===this.account).map(s=>s.endpoint).filter((s):s is string=>!!s))]}
  nodes(){return [...new Set((this.catalog()?.nodes||[]).filter(s=>!this.host||s.host_scope===this.host).map(s=>s.node_id))]}
  trafficResult=computed(()=>this.displayBatch()?.results[0]||this.displayBatch()?.results[3]||(this.kind!=='dns'?this.displayBatch()?.results[4]:undefined));
  dnsResult=computed(()=>this.displayBatch()?.results[1]||(this.kind==='dns'?this.displayBatch()?.results[4]:undefined));
  summary=computed<Fact|undefined>(()=>{
    const data=this.displayBatch()?.results[0]?.data;
    return this.page()==='Sources & health'?(data?.domain==='operational-not-network-activity'?{source_health:data}:undefined):data;
  });
  dnsSummary=computed(()=>this.displayBatch()?.results[1]?.data);
  bins=computed(()=>this.displayBatch()?.results[2]?.data.bins as Bin[]||[]);
  dnsBins=computed(()=>this.displayBatch()?.results[7]?.data.bins as Bin[]||[]);
  applications=computed(()=>this.displayBatch()?.results[3]?.data.groups as Fact[]||[]);
  factsResult=computed(()=>this.batch()?.results[4]);rows=computed(()=>this.factsResult()?.data.rows as Fact[]||[]);
  groups=computed(()=>this.batch()?.results[5]?.data.groups as Fact[]||[]);
  policies=computed(()=>this.batch()?.results[6]?.data.rows as Fact[]||[]);
  processName=applicationName;
  consumers=computed(()=>this.applications().map(r=>({value:r.keys.application,label:applicationName(r.keys.application_path),fullPath:r.keys.application_path,
    inbound_bytes:r.inbound_bytes,outbound_bytes:r.outbound_bytes,total_bytes:r.total_bytes,bucket_count:r.count} as Consumer)));
  destinations=computed(()=>this.summary()?.top_destinations as Consumer[]||[]);
  questions=computed(()=>this.dnsSummary()?.dns_questions.ranking as Fact[]||[]);
  outcomes=computed(()=>Object.entries(this.dnsSummary()?.dns_outcomes.counts||{}).map(([name,count])=>({name,count:Number(count)})));
  correlation=computed(()=>{const rows=this.summary()?.correlation_coverage||{},total=exact(this.summary()?.data.total_bytes);
    return Object.entries(rows).map(([name,v])=>{const value=v as Fact;return {name,bytes:value.total_bytes,count:value.bucket_count,weight:total?Number(exact(value.total_bytes))/Number(total)*100:0}})});
  constructor(){this.setTime();void this.initialize()}
  skipContent(){document.getElementById('analytics-main')?.focus()}
  async initialize(){this.busy.set(true);try{
    this.runtime.set(await command<State>('state'));this.catalog.set(await command<Catalog>('view-catalog'));
    this.retentionDays=this.catalog()!.health.retention_days;
    this.saved.set((await command<{queries:Saved[]}>('saved-query',{action:'list'})).queries);
  }catch(e){this.error.set((e as Error).message)}finally{this.busy.set(false)}await this.refresh()}
  private setTime(){Object.assign(this,presetBounds(this.range))}
  localTime(value:string){return Number.isFinite(Date.parse(value))?new Date(value).toLocaleString():'Invalid timestamp'}
  utc(value:number|string){const n=Number(value);return Number.isFinite(n)?new Date(n/1000).toISOString():'Unavailable'}
  scope(){return {...(this.host?{host:this.host}:{}),...(this.device?{device:this.device}:{}),...(this.account?{account:this.account}:{}),...(this.endpoint?{endpoint:this.endpoint}:{})}}
  filter(kind:string):Predicate|undefined{
    const leaves=this.predicates;
    // DNS views deliberately have their own predicate domain; do not silently
    // apply application constraints to unrelated endpoint DNS totals.
    const allowed=new Set(fields[kind as Kind]||[]);
    const compatible=leaves.every(p=>this.predicateFields(p).every(f=>allowed.has(f)));
    const common=compatible&&leaves.length?{[this.combine]:leaves}:undefined;
    if(kind!=='dns'&&this.application()!==undefined){const app={field:'application',op:'eq',value:this.application()};return common?{all:[app,common]}:app}
    return common;
  }
  groupScope(value:unknown){const field=this.group;this.group='';this.constrain({field,op:'eq',value});void this.scopeChanged()}
  constrain(predicate:Predicate){const current=this.predicates.length?{[this.combine]:[...this.predicates]}:null;
    this.predicates=current?[current,predicate]:[predicate];this.combine='all'}
  predicateFields(p:Predicate):string[]{return p.field?[p.field]:[...(p.all||p.any||[])].flatMap(c=>this.predicateFields(c))}
  query(kind:string,view:string):Query{
    const query:Query={kind,view,start:this.start,end:this.end,scope:this.scope()};
    if(kind==='dns'||kind==='policy')delete query.scope.device;
    if(['traffic','dns','correlations'].includes(kind)){
      const predicate=this.filter(kind);if(predicate)query.where=predicate;
      if(this.search&&(!this.predicates.length||this.predicates.every(p=>this.predicateFields(p).every(f=>(fields[kind as Kind]||[]).includes(f)))))query.search=this.search;
    }return query;
  }
  async refresh(newTime=false,revision?:number){
    if(this.busy())return;this.busy.set(true);this.ready.set(false);this.error.set('');this.pendingBatch.set(null);const generation=++this.loadingGeneration;
    const focused=newTime&&this.selected()?'fact-'+this.selected():document.activeElement instanceof HTMLElement?document.activeElement.id:'';
    try{
      if(newTime){if(this.range!=='custom')this.setTime();this.pageIndex=0;this.cursors=[undefined]}
      if(!/^\d{4}-\d\d-\d\dT.*Z$/.test(this.start)||!/^\d{4}-\d\d-\d\dT.*Z$/.test(this.end)||Date.parse(this.start)>=Date.parse(this.end))throw new Error('Use ascending RFC 3339 UTC timestamps ending in Z.');
      if(this.page()==='Settings'){
        this.catalog.set(await command<Catalog>('view-catalog'));this.runtime.set(await command<State>('state'));this.batch.set(null);this.ready.set(true);return;
      }
      const selectedKind=this.kind;
      const traffic=this.query('traffic','summary'),dns=this.query('dns','summary'),series=this.query('traffic','series');
      // A DNS-specific explorer filter can select traffic by candidate existence;
      // incompatible traffic-only predicates never masquerade as DNS filtering.
      series.bin_seconds=Math.max(1,Math.min(86400,Math.ceil((Date.parse(this.end)-Date.parse(this.start))/1000/120)));
      const dnsSeries={...this.query('dns','series'),bin_seconds:series.bin_seconds};
      const apps={...this.query('traffic','groups'),group_by:['application','application_path'],order_by:[{field:'total_bytes',direction:'desc'}]};
      const facts:Query={...this.query(selectedKind,'facts'),limit:50,order_by:[{field:this.order.split(':')[0],direction:this.order.split(':')[1]}],
        ...(newTime&&this.selected()?{anchor_id:this.selected()}:this.cursors[this.pageIndex]?{cursor:this.cursors[this.pageIndex]}:{})};
      const groups={...this.query(selectedKind,'groups'),group_by:[this.group||(selectedKind==='dns'?'question':'application_path')],order_by:[{field:'count',direction:'desc'}]};
      const policy={...this.query('policy','facts'),limit:100,order_by:[{field:'timestamp',direction:'desc'}]};
      // Query only this page's required fact domain, still in one read revision.
      // Policy/history controls must not load unrelated network facts or inherit
      // their resource limits. No empty result is substituted for an unread view.
      const planned:Record<number,Query>={0:traffic,1:dns,2:series,3:apps,4:facts,5:groups,6:policy,7:dnsSeries};
      const indices=this.page()==='Overview'||this.page()==='Applications'&&this.application()!==undefined?[0,1,2,3,7]:
        this.page()==='Applications'?[3]:this.page()==='Control D'?[6]:this.page()==='Sources & health'?[0]:
        [...(this.kind==='dns'?[]:[2]),4,...(this.group?[5]:[])];
      if(this.page()==='Sources & health')planned[0]={...traffic,view:'health'};
      const result=await command<Batch>('view-query',{queries:indices.map(i=>planned[i]),...(revision===undefined?{}:{revision})},event=>{
        if(generation===this.loadingGeneration)this.pendingBatch.set(mergeProgress(this.pendingBatch(),event as BatchProgress,indices) as Batch);
      });
      if(generation!==this.loadingGeneration)return;
      const ordered:Result[]=[];indices.forEach((i,j)=>ordered[i]=result.results[j]);
      const state=await command<State>('state');if(generation!==this.loadingGeneration)return;
      this.batch.set({...result,results:ordered});this.runtime.set(state);
      if(ordered[4]){this.pageIndex=Math.floor(ordered[4].data.page_offset/50);
        this.cursors[this.pageIndex]=ordered[4].data.current_cursor||undefined;
        this.lastQuery={...facts};delete this.lastQuery.cursor;delete this.lastQuery.anchor_id;}
      this.ready.set(true);
      if(focused)requestAnimationFrame(()=>document.getElementById(focused)?.focus());
    }catch(e){if(generation===this.loadingGeneration)this.error.set((e as Error).message)}finally{
      this.pendingBatch.set(null);this.finishOperation();
    }
  }
  async navigate(page:Page){this.page.set(page);this.notice.set('');
    this.pageIndex=0;this.cursors=[undefined];
    if(page==='Applications'){this.kind='traffic';this.group=''}
    if(this.busy()){this.loadingGeneration++;this.queuedNavigation=true;this.pendingBatch.set(null);this.batch.set(null);return}
    await this.scopeChanged();}
  async scopeChanged(){this.pageIndex=0;this.cursors=[undefined];await this.refresh()}
  finishOperation(){this.busy.set(false);if(this.queuedNavigation){this.queuedNavigation=false;void this.refresh()}}
  hostChanged(){if(this.device&&!this.nodes().includes(this.device))this.device='';void this.scopeChanged()}
  timeChanged(){if(this.range!=='custom')this.setTime();void this.scopeChanged()}
  customTime(){this.range='custom';void this.scopeChanged()}
  accountChanged(){this.endpoint='';void this.scopeChanged()}
  availableHistory(){const values=Object.values(this.catalog()?.intervals||{}).filter(v=>v.start&&v.end);if(!values.length)return;
    this.end=values.map(v=>v.end!).sort().at(-1)!;const first=values.map(v=>v.start!).sort()[0];
    this.start=new Date(Math.max(Date.parse(first),Date.parse(this.end)-3600000)).toISOString();this.range='custom';void this.scopeChanged()}
  providerSources(){return (this.catalog()?.sources||[]).filter(s=>s.kind==='dns')}
  runtimeSources(){return Object.entries(this.runtime()?.sources||{}).map(([name,value])=>({name,value}))}
  appName(id:string|null|undefined){return applicationName(id===this.application()&&this.applicationLabel()?this.applicationLabel():this.applications().find(r=>r.keys.application===id)?.keys.application_path)}
  openApplication(id:string|null){this.applicationLabel.set(this.applications().find(r=>r.keys.application===id)?.keys.application_path||'Unknown executable');this.application.set(id);this.kind='traffic';this.page.set('Applications');void this.scopeChanged()}
  clearApplication(){this.application.set(undefined);this.applicationLabel.set('');void this.scopeChanged()}
  explore(kind:Kind,group=''){if(kind==='dns')this.independentDns();this.kind=kind;this.field=kind==='dns'?'question':'application_path';this.group=group;this.order='timestamp:desc';this.page.set('Activity');void this.scopeChanged()}
  selectConsumer(row:Consumer){if(this.application()===undefined)this.openApplication(row.value);else this.destinationScope(row.value)}
  destinationScope(value:string|null){this.kind='traffic';this.constrain({field:'destination_ip',op:'eq',value});this.explore('traffic')}
  independentDns(){this.application.set(undefined);if(this.predicates.some(p=>this.predicateFields(p).some(f=>!fields.dns.includes(f))))this.predicates=[]}
  questionScope(value:string|null){this.independentDns();this.constrain({field:'question',op:'eq',value});this.explore('dns')}
  candidateQuestionScope(value:string){this.constrain({field:'question',op:'eq',value});this.explore('traffic')}
  geographyScope(field:string,value:string|null){this.constrain({field,op:'eq',value});this.explore('traffic')}
  selectGeography(field:'country'|'asn',value:string|null){if(this.geographyMode()==='dns'){
    this.independentDns();this.constrain({field:'provider_'+field,op:'eq',value});this.explore('dns');
  }else this.geographyScope('destination_'+field,value)}
  correlationScope(value:string){this.constrain({field:'correlation_state',op:'eq',value});this.explore('correlations')}
  outcomeScope(value:string){this.independentDns();this.constrain({field:'outcome',op:'eq',value});this.explore('dns')}
  binScope(bin:Bin){this.start=bin.scope_start||bin.start;this.end=bin.scope_end||bin.end;this.range='custom';this.explore('traffic')}
  dnsBinScope(bin:Bin){this.start=bin.scope_start||bin.start;this.end=bin.scope_end||bin.end;this.range='custom';this.explore('dns')}
  setKind(kind:Kind){if(this.busy())return;
    if(this.predicates.some(p=>this.predicateFields(p).some(f=>!fields[kind].includes(f)))){this.error.set('Remove incompatible filters before switching fact mode.');return}
    if(kind==='dns'&&this.application()!==undefined){this.error.set('Remove application scope before opening independent endpoint DNS facts.');return}
    this.kind=kind;this.field=fields[kind][0];this.group='';this.order='timestamp:desc';void this.scopeChanged()}
  filterFields(){return fields[this.kind]}
  groupFields(){return fields[this.kind].filter(f=>this.kind==='dns'||!fields.dns.includes(f))}
  operators(){return numeric.has(this.field)?['eq','ne','gt','gte','lt','lte','in']:['eq','ne','contains','in']}
  addFilter(){if(this.busy())return;
    let value:unknown=this.filterValue==='null'?null:this.filterValue;
    if(this.operator==='in'){try{value=JSON.parse(this.filterValue)}catch{this.error.set('For “in”, enter a JSON array of literal values.');return}}
    if(numeric.has(this.field)&&value!==null&&this.operator!=='in'&&!/^-?\d{1,20}$/.test(String(value))){this.error.set('Use an exact decimal integer.');return}
    if(!this.operators().includes(this.operator)){this.error.set('Operator is unsupported for this field.');return}
    this.predicates.push({field:this.field,op:this.operator,value});this.filterValue='';void this.scopeChanged()}
  predicateLabel(p:Predicate){return p.field?`${p.field} ${p.op} ${typeof p.value==='object'?JSON.stringify(p.value):p.value}`:JSON.stringify(p)}
  removeFilter(i:number){this.predicates.splice(i,1);void this.scopeChanged()}
  clearSearch(){this.search='';void this.scopeChanged()}
  async nextPage(){if(!this.factsResult()?.data.next_cursor)return;const next=this.factsResult()!.data.next_cursor;
    this.cursors[this.pageIndex+1]=next;this.pageIndex++;await this.refresh(false,this.batch()?.revision)}
  async previousPage(){if(this.pageIndex>0){const previous=this.factsResult()?.data.previous_cursor;this.pageIndex--;this.cursors[this.pageIndex]=previous;await this.refresh(false,this.batch()?.revision)}}
  trackRow(_:number,row:Fact){return row.id}
  rowToggled(row:Fact,event:Event){if((event.target as HTMLDetailsElement).open)this.selected.set(row.id);else if(this.selected()===row.id)this.selected.set('')}
  async exportFacts(format:'json'|'csv'){if(!this.lastQuery||!this.batch()||this.busy())return;this.busy.set(true);this.error.set('');
    try{const result=await command<Fact>('export-query',{query:this.lastQuery,revision:this.batch()!.revision,format});
      this.notice.set(result.cancelled?'Export cancelled.':`Saved ${result.name}: ${result.row_count} facts, revision ${result.revision}${result.coverage_incomplete?' · partial coverage':''}.`)}
    catch(e){this.error.set((e as Error).message)}finally{this.finishOperation()}}
  async saveQuery(){if(!this.lastQuery)return;const query={...this.lastQuery};
    if(this.group){query.view='groups';query.group_by=[this.group];delete query.limit;query.order_by=[{field:'count',direction:'desc'}]}
    this.busy.set(true);try{this.saved.set((await command<{queries:Saved[]}>('saved-query',{action:'save',name:this.savedName.trim(),query})).queries);this.notice.set('Saved locally. No account data uploaded.')}
    catch(e){this.error.set((e as Error).message)}finally{this.finishOperation()}}
  async openSaved(){const saved=this.saved().find(s=>s.name===this.savedSelection);if(!saved)return;const q=saved.query;
    this.application.set(undefined);this.start=q.start;this.end=q.end;this.range='custom';this.host=q.scope.host||'';this.device=q.scope.device||'';this.account=q.scope.account||'';this.endpoint=q.scope.endpoint||'';
    this.kind=q.kind as Kind;this.field=fields[this.kind][0];this.search=q.search||'';this.predicates=q.where?[q.where]:[];this.combine='all';this.group=q.view==='groups'?q.group_by?.[0]||'':'';
    this.order=q.view==='facts'&&q.order_by?`${q.order_by[0].field}:${q.order_by[0].direction}`:'timestamp:desc';await this.scopeChanged()}
  async removeSaved(){this.busy.set(true);try{this.saved.set((await command<{queries:Saved[]}>('saved-query',{action:'remove',name:this.savedSelection})).queries);this.savedSelection=''}catch(e){this.error.set((e as Error).message)}finally{this.finishOperation()}}
  resourceEntries(value:Fact){return Object.entries(value||{}).map(([name,value])=>({name,value:value as Fact}))}
  policyIdentity(policy:Fact){const {resources,...identity}=policy;return identity}
  async retentionChanged(){if(this.busy())return;if(!Number.isInteger(this.retentionDays)||this.retentionDays<1||this.retentionDays>3650){this.error.set('Retention must be 1–3650 days.');return}
    await this.historyCommand('retention',{days:this.retentionDays})}
  cleanupHistory(){return this.historyCommand('cleanup')}
  async deleteHistory(){if(!this.confirmDelete)return;const scope:Fact={kind:this.deleteKind,start:this.start,end:this.end};
    if(this.deleteKind==='traffic'&&this.application()!==undefined){const path=this.applications().find(r=>r.keys.application===this.application())?.keys.application_path;
      if(!path){this.error.set('Unknown application identity cannot be deleted by executable path. Remove the application scope to delete the interval.');return}scope.application_path=path}
    // Deletion API is interval/source based, not arbitrary account filtering.
    if(this.host||this.device||this.account||this.endpoint||this.predicates.length||this.search){this.error.set('Clear host/node/account/endpoint and explorer filters before interval deletion. No broader deletion was performed.');return}
    this.confirmDelete=false;await this.historyCommand(this.deleteKind==='context'||this.deleteKind==='policy'?'delete-snapshots':'delete',scope)}
  async historyCommand(op:string,body:unknown={}){if(this.busy())return;this.busy.set(true);let success=false;
    try{await command(op,body);this.catalog.set(await command<Catalog>('view-catalog'));this.notice.set('Local history updated. External sources are unchanged.');success=true}
    catch(e){this.error.set((e as Error).message)}finally{this.busy.set(false)}if(success)await this.scopeChanged()}
}
bootstrapApplication(App,{providers:[provideZonelessChangeDetection()]}).catch(()=>{
  document.body.textContent='TailD could not start its local analytics. Reopen the application.';
});
