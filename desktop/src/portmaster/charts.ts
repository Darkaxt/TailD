// SPDX-License-Identifier: GPL-3.0-only
// Adapted from Safing Portmaster line-chart / circular-bar-chart; see NOTICE.md.
import {AfterViewInit,Component,DestroyRef,ElementRef,EventEmitter,Input,Output,inject} from '@angular/core';
import {CommonModule} from '@angular/common';
import * as d3 from 'd3';

export const exact=(value:unknown):bigint=>BigInt(value==null?'0':String(value));
export function bytes(value:unknown):string{
  if(value==null)return 'Unavailable';
  const n=exact(value),units=['B','KiB','MiB','GiB','TiB','PiB','EiB'];
  let divisor=1n,index=0;
  while(n>=divisor*1024n&&index<units.length-1){divisor*=1024n;index++}
  return index?`${n/divisor}.${(n%divisor)*10n/divisor} ${units[index]}`:`${n} B`;
}
export interface Bin {start:string;end:string;inbound_bytes:string;outbound_bytes:string;total_bytes:string;
  coverage_incomplete:boolean;represented_microseconds:number;rate:unknown|null}
export interface Consumer {value:string|null;label?:string;fullPath?:string;inbound_bytes:string;outbound_bytes:string;total_bytes:string;bucket_count?:number}

@Component({selector:'sfng-netquery-line-chart',standalone:true,imports:[CommonModule],
  template:`<div class="chart-legend"><span class="received">● Received</span><span class="sent">● Sent</span>
    <button [attr.aria-pressed]="mode==='bytes'" (click)="changeMode('bytes')">Bytes / bin</button>
    <button [attr.aria-pressed]="mode==='rate'" (click)="changeMode('rate')">B/s</button>
    <span>Gaps are unobserved · partial values are lower bounds</span></div>
    <div class="line-surface" #surface></div>
    <p *ngIf="!hasValues" class="chart-empty">No measured {{mode==='rate'?'complete-bin rates':'traffic'}} in this scope. Missing coverage is not zero.</p>
    <details class="chart-data"><summary>Exact chart data · UTC</summary><div class="table-scroll"><table>
      <thead><tr><th>UTC bin</th><th>Received bytes</th><th>Sent bytes</th><th>Coverage</th><th>Rate</th></tr></thead>
      <tbody><tr *ngFor="let bin of bins"><td><button (click)="select.emit(bin)">{{bin.start}}</button></td>
        <td>{{bin.inbound_bytes}}</td><td>{{bin.outbound_bytes}}</td><td>{{bin.coverage_incomplete?'Partial / unobserved':'Observed'}}</td>
        <td>{{bin.rate===null?'Unavailable':bin.total_bytes+' bytes / '+bin.represented_microseconds+' μs'}}</td></tr></tbody>
    </table></div></details>`,
  styles:[`:host{display:block;position:relative}.line-surface{height:280px;width:100%}.chart-empty{position:absolute;top:130px;left:64px;right:64px;text-align:center}`]})
export class SfngNetqueryLineChartComponent implements AfterViewInit {
  private element=inject(ElementRef<HTMLElement>);private destroy=inject(DestroyRef);private ready=false;
  @Input() set data(value:Bin[]){this.bins=value||[];this.redraw()}
  @Output() select=new EventEmitter<Bin>();
  bins:Bin[]=[];mode:'bytes'|'rate'='bytes';hasValues=false;
  changeMode(mode:'bytes'|'rate'){this.mode=mode;this.redraw()}
  ngAfterViewInit(){this.ready=true;const observer=new ResizeObserver(()=>this.redraw());
    observer.observe(this.element.nativeElement);this.destroy.onDestroy(()=>observer.disconnect());this.redraw()}
  redraw(){
    if(!this.ready)return;
    const surface=this.element.nativeElement.querySelector('.line-surface')!;
    d3.select(surface).selectAll('svg').remove();
    const width=Math.max(200,surface.getBoundingClientRect().width),height=280,margin={left:60,right:20,top:24,bottom:38};
    const svg=d3.select(surface).append('svg').attr('width','100%').attr('height',height)
      .attr('role','img').attr('aria-label','Sent and received traffic. Exact values and scope links in chart data table.');
    const x=d3.scaleUtc().range([margin.left,width-margin.right]).domain(this.bins.length?
      [new Date(this.bins[0].start),new Date(this.bins[this.bins.length-1].end)]:[new Date(0),new Date(60000)]);
    const value=(b:Bin,key:'inbound_bytes'|'outbound_bytes'):number|null=>{
      if(this.mode==='rate'&&b.rate===null)return null;
      if(this.mode==='bytes'&&b.coverage_incomplete&&exact(b.total_bytes)===0n)return null;
      const observed=Number(exact(b[key]));return this.mode==='rate'?observed*1000000/b.represented_microseconds:observed;
    };
    const max=d3.max(this.bins,b=>Math.max(value(b,'inbound_bytes')||0,value(b,'outbound_bytes')||0))||0;
    this.hasValues=this.bins.some(b=>value(b,'inbound_bytes')!==null||value(b,'outbound_bytes')!==null);
    const y=d3.scaleLinear().range([height-margin.bottom,margin.top]).domain([0,max>0?max*1.15:1]);
    svg.append('g').attr('transform',`translate(0,${height-margin.bottom})`).call(d3.axisBottom(x).ticks(5).tickFormat(d=>d3.utcFormat('%H:%M')(d as Date)));
    svg.append('g').attr('transform',`translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(4).tickFormat(d=>d3.format('.2s')(Number(d))+(this.mode==='rate'?'/s':'')));
    for(const [key,color] of [['inbound_bytes','#85aaf5'],['outbound_bytes','#b7a7ec']] as const){
      const line=d3.line<Bin>().defined(b=>value(b,key)!==null).x(b=>x(new Date(b.start))).y(b=>y(value(b,key)!)).curve(d3.curveLinear);
      const area=d3.area<Bin>().defined(b=>value(b,key)!==null).x(b=>x(new Date(b.start))).y0(height-margin.bottom).y1(b=>y(value(b,key)!)).curve(d3.curveLinear);
      svg.append('path').datum(this.bins).attr('fill',color).attr('opacity',.09).attr('d',area);
      svg.append('path').datum(this.bins).attr('fill','none').attr('stroke',color).attr('stroke-width',1.5).attr('d',line);
      svg.append('g').selectAll('circle').data(this.bins.filter(b=>value(b,key)!==null)).join('circle')
        .attr('cx',b=>x(new Date(b.start))).attr('cy',b=>y(value(b,key)!)).attr('r',3).attr('fill',color)
        .on('click',(_,b)=>this.select.emit(b)).append('title')
        .text(b=>`${b.start} – ${b.end}\n${key==='inbound_bytes'?'Received':'Sent'}: ${b[key]} bytes\n${b.coverage_incomplete?'Partial / lower bound':'Observed'}; rate ${b.rate===null?'unavailable':'sampled, not instantaneous'}`);
    }
  }
}

@Component({selector:'sfng-netquery-circular-bar-chart',standalone:true,imports:[CommonModule],
  template:`<div class="radial-surface"></div><div class="consumer-list" role="list">
    <div *ngFor="let row of rows;let i=index" role="listitem"><button class="consumer" (click)="select.emit(row)"
      [title]="(row.fullPath||row.label||row.value||'Unknown')+' · '+row.total_bytes+' bytes'">
      <span class="rank">{{i+1}}</span><span class="consumer-name">{{row.label||row.value||'Unknown identity'}}</span>
      <span>{{format(row.total_bytes)}}</span><span class="consumer-bar"><span [style.width.%]="share(row.inbound_bytes)" class="in"></span>
      <span [style.width.%]="share(row.outbound_bytes)" class="out"></span></span>
    </button></div></div><p class="hint" *ngIf="!rows.length">No observed consumers in this scope.</p>`,
  styles:[`:host{display:grid;grid-template-columns:minmax(220px,1fr) minmax(220px,1fr);gap:16px}.radial-surface{height:320px}.consumer-list{max-height:320px;overflow:auto}.consumer{display:grid;grid-template-columns:20px minmax(0,1fr) auto;gap:8px;width:100%;text-align:left;border:0;border-radius:0;background:none;padding:8px 0}.consumer-name{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.rank{color:var(--text-tertiary)}.consumer-bar{grid-column:2/-1;display:flex;height:3px;overflow:hidden}.in{background:#85aaf5}.out{background:#b7a7ec}@media(max-width:1100px){:host{grid-template-columns:1fr}.radial-surface{height:260px}}`]})
export class CircularBarChartComponent implements AfterViewInit {
  private element=inject(ElementRef<HTMLElement>);private destroy=inject(DestroyRef);private ready=false;
  @Input() set data(value:Consumer[]){this.rows=value||[];this.render()}
  @Output() select=new EventEmitter<Consumer>();
  rows:Consumer[]=[];format=bytes;
  share(value:string){const max=this.rows.reduce((n,r)=>exact(r.total_bytes)>n?exact(r.total_bytes):n,0n);
    return max>0n?Number(exact(value)*10000n/max)/100:0}
  ngAfterViewInit(){this.ready=true;const observer=new ResizeObserver(()=>this.render());observer.observe(this.element.nativeElement);
    this.destroy.onDestroy(()=>observer.disconnect());this.render()}
  render(){
    if(!this.ready)return;
    const surface=this.element.nativeElement.querySelector('.radial-surface')!;
    d3.select(surface).selectAll('svg').remove();
    const box=surface.getBoundingClientRect(),width=Math.max(200,box.width),height=box.height;
    // Retain Portmaster's indexed stack -> radial scale -> arc -> ticks/legend.
    // All rows remain in the companion list; combine only plotted tail consumers.
    const plot=this.rows.slice(0,8);
    if(this.rows.length>8){const rest=this.rows.slice(8);plot.push({value:'Other consumers (plot only)',
      inbound_bytes:String(rest.reduce((n,r)=>n+exact(r.inbound_bytes),0n)),outbound_bytes:String(rest.reduce((n,r)=>n+exact(r.outbound_bytes),0n)),
      total_bytes:String(rest.reduce((n,r)=>n+exact(r.total_bytes),0n))})}
    const indexed=d3.index(plot.map((r,i)=>({...r,key:String(i)})),r=>r.key);
    const stack=d3.stack<[string,Consumer]>().keys(['inbound_bytes','outbound_bytes']).value((entry,key)=>Number(exact(entry[1][key as 'inbound_bytes'|'outbound_bytes'])));
    const series=stack(indexed),outerRadius=Math.min(width,height)/2-28,innerRadius=Math.min(55,outerRadius*.45);
    const x=d3.scaleBand<string>().range([0,2*Math.PI]).align(0).domain([...indexed.keys()]);
    const highest=d3.max(series,s=>d3.max(s,p=>p[1]))||1;
    const y=d3.scaleRadial().domain([0,highest]).range([innerRadius,outerRadius]);
    const svg=d3.select(surface).append('svg').attr('width','100%').attr('height','100%').attr('role','img')
      .attr('aria-label','Ranked sent and received stacked consumer chart. Use the adjacent accessible list to inspect each consumer.')
      .append('g').attr('transform',`translate(${width/2},${height/2})`);
    const arc=d3.arc<d3.SeriesPoint<[string,Consumer]>>().innerRadius(d=>y(d[0])).outerRadius(d=>y(d[1]))
      .startAngle(d=>x(d.data[0])!).endAngle(d=>x(d.data[0])!+x.bandwidth()).padAngle(.015).padRadius(innerRadius);
    svg.append('g').selectAll('g').data(series).join('g').attr('fill',s=>s.key==='inbound_bytes'?'#85aaf5':'#b7a7ec')
      .selectAll('path').data(s=>s.map(p=>Object.assign(p,{series:s.key}))).join('path').attr('d',arc)
      .on('click',(_,d)=>{if(Number(d.data[0])<8)this.select.emit(this.rows[Number(d.data[0])])})
      .append('title').text(d=>`${d.data[1].label||d.data[1].value||'Unknown'}${d.data[1].fullPath?'\n'+d.data[1].fullPath:''}\nReceived ${d.data[1].inbound_bytes} bytes\nSent ${d.data[1].outbound_bytes} bytes`);
    svg.append('g').attr('text-anchor','middle').selectAll('g').data(y.ticks(3).slice(1)).join('g')
      .call(g=>g.append('circle').attr('stroke','#fff').attr('stroke-opacity',.15).attr('fill','none').attr('r',y))
      .call(g=>g.append('text').attr('y',d=>-y(d)).attr('dy','.35em').attr('fill','currentColor').attr('font-size',10).text(d=>d3.format('.2s')(d)));
    svg.append('g').selectAll('g').data(['Received','Sent']).join('g').attr('transform',(_,i)=>`translate(-32,${i*20-6})`)
      .call(g=>g.append('circle').attr('r',4).attr('fill',(_,i)=>i===0?'#85aaf5':'#b7a7ec'))
      .call(g=>g.append('text').attr('x',10).attr('y',4).attr('font-size',10).attr('fill','currentColor').text(d=>d));
  }
}
