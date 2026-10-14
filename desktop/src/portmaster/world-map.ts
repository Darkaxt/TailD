// SPDX-License-Identifier: GPL-3.0-only
// Safing Portmaster map-renderer b794a8c: Mercator/TopoJSON country paths and
// owned resize lifecycle. No SPN handlers, routes, remote assets or fake pins.
import {AfterViewInit,Component,DestroyRef,ElementRef,EventEmitter,Input,Output,inject,signal} from '@angular/core';
import {CommonModule} from '@angular/common';
import {geoMercator,geoPath,select} from 'd3';
import {feature} from 'topojson-client';
import type {Topology,GeometryCollection} from 'topojson-specification';
import type {FeatureCollection,Geometry} from 'geojson';
import {Consumer,bytes,exact} from './charts';

@Component({selector:'taild-world-map',standalone:true,imports:[CommonModule],
  template:`<div class="map-surface" [attr.data-map-ready]="ready()" role="group" aria-label="Inferred answer-country map"></div>
    <p class="hint" role="status" *ngIf="!ready()&&!failed()">Loading packaged country map…</p>
    <p class="hint" role="status" *ngIf="failed()">Country map unavailable. Use the country table.</p>
    <div class="map-key"><span><i></i> Inferred candidate bytes</span><span>Unobserved countries stay neutral</span></div>
    <p class="hint">Control D answer metadata · unique temporal candidates, not measured routes or device location.</p>
    <p class="hint" *ngIf="unmapped()>0n">Unknown / unmapped: {{format(unmapped())}}. Retained in the country table.</p>`,
  styles:[`:host{display:block;min-width:0}.map-surface{height:340px;background:#1f1e1e;border-radius:4px;overflow:hidden}
    .map-key{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:12px 0;font-size:10px;color:var(--text-tertiary)}
    i{display:inline-block;width:8px;height:8px;background:#4b70cc;margin-right:5px}
    .map-surface ::ng-deep path{fill:#3b3939;stroke:#1f1e1e;stroke-width:.7;stroke-linejoin:round}
    .map-surface ::ng-deep path.observed{fill:#4b70cc;cursor:pointer}
    .map-surface ::ng-deep path.observed:hover,.map-surface ::ng-deep path.observed:focus{fill:#85aaf5;stroke:#f9f7f6;outline:none}
    .map-surface ::ng-deep path.highlighted{fill:#85aaf5;stroke:#f9f7f6}
    @media(max-width:850px){.map-surface{height:300px}}`]})
export class WorldMapComponent implements AfterViewInit {
  private element=inject(ElementRef<HTMLElement>);private destroy=inject(DestroyRef);private disposed=false;
  private countries:FeatureCollection<Geometry,{iso_a2:string;name:string}>|null=null;
  private rows:Consumer[]=[];ready=signal(false);failed=signal(false);unmapped=signal(0n);format=bytes;
  @Output() selectCountry=new EventEmitter<string>();
  private highlighted:string|null=null;
  @Input() set highlightedCountry(value:string|null){this.highlighted=value;this.highlight()}
  @Input() set data(value:Consumer[]){this.rows=value||[];this.render()}
  private highlight(){const value=this.highlighted;select(this.element.nativeElement).selectAll<SVGPathElement,unknown>('path[data-country]')
    .classed('highlighted',function(){return this.getAttribute('data-country')===value})}
  async ngAfterViewInit(){
    this.destroy.onDestroy(()=>{this.disposed=true});
    try{
      // Lazy bundled data: fixed-origin JS only, no fetch or CSP relaxation.
      const module=await import('./world-50m.json');
      if(this.disposed)return;
      const world=module.default as unknown as Topology<{countries:GeometryCollection<{iso_a2:string;name:string}>}>;
      this.countries=feature(world,world.objects.countries);
      const observer=new ResizeObserver(()=>this.render());observer.observe(this.element.nativeElement);
      this.destroy.onDestroy(()=>observer.disconnect());this.render();
    }catch{if(!this.disposed)this.failed.set(true)}
  }
  private render(){
    if(!this.countries||this.disposed)return;
    const surface=this.element.nativeElement.querySelector('.map-surface') as HTMLElement|null;if(!surface)return;
    const size=surface.getBoundingClientRect();if(!size.width||!size.height)return;
    const countries={...this.countries,features:this.countries.features.filter(c=>c.properties.iso_a2!=='AQ')};
    const codes=new Set(countries.features.map(c=>c.properties.iso_a2));
    this.unmapped.set(this.rows.filter(r=>!r.value||!codes.has(r.value)).reduce((n,r)=>n+exact(r.total_bytes),0n));
    const values=new Map(this.rows.filter(r=>r.value&&codes.has(r.value)).map(r=>[r.value,exact(r.total_bytes)]));
    const projection=geoMercator().rotate([0,0]).fitExtent([[8,8],[size.width-8,size.height-8]],countries);
    const path=geoPath().projection(projection);
    select(surface).selectAll('svg').remove();
    const svg=select(surface).append('svg').attr('width','100%').attr('height','100%').attr('aria-label','Answer-country geography; country table provides equivalent keyboard actions');
    const paths=svg.append('g').attr('id','world-group').selectAll('path').data(countries.features).join('path')
      .attr('data-country',d=>d.properties.iso_a2).attr('d',path)
      .classed('observed',d=>(values.get(d.properties.iso_a2)||0n)>0n)
      .attr('tabindex',d=>(values.get(d.properties.iso_a2)||0n)>0n?0:null)
      .attr('role',d=>(values.get(d.properties.iso_a2)||0n)>0n?'button':null)
      .attr('aria-label',d=>`${d.properties.name}: ${values.has(d.properties.iso_a2)?values.get(d.properties.iso_a2)+' inferred candidate bytes':'unobserved'}`)
      .on('click',(_,d)=>{if((values.get(d.properties.iso_a2)||0n)>0n)this.selectCountry.emit(d.properties.iso_a2)})
      .on('keydown',(event:KeyboardEvent,d)=>{if((event.key==='Enter'||event.key===' ')&&(values.get(d.properties.iso_a2)||0n)>0n){event.preventDefault();this.selectCountry.emit(d.properties.iso_a2)}});
    paths.append('title').text(d=>`${d.properties.name} · ${values.has(d.properties.iso_a2)?values.get(d.properties.iso_a2)+' inferred bytes':'No geography observed'}`);
    this.highlight();this.ready.set(true);
  }
}
