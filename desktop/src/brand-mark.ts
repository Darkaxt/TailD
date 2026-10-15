// SPDX-License-Identifier: GPL-3.0-only
// Component code only. Product marks retain their owners' rights; see NOTICE.md.
import {Component,Input,ChangeDetectionStrategy} from '@angular/core';

export type Brand='tailscale'|'controld';

@Component({selector:'taild-brand-mark',standalone:true,
  host:{'aria-hidden':'true','class':'brand-mark','[attr.data-brand]':'brand'},
  template:`
    @if(brand==='controld') {
      <svg viewBox="0 0 44 33" fill="currentColor" focusable="false" aria-hidden="true">
        <path d="M1.43568 15.5C0.569739 15.5 -0.122974 14.7664 0.0184833 13.9121C1.27789 6.30615 7.95207 0.5 16.1713 0.5H19.5514C20.2615 0.5 20.8371 1.07563 20.8371 1.78571C20.8371 9.35991 14.697 15.5 7.1228 15.5H1.43568Z" />
        <path d="M1.43561 17.5C0.569673 17.5 -0.123043 18.2336 0.018416 19.0879C1.27783 26.6938 7.95207 32.5 16.1713 32.5H19.5514C20.2615 32.5 20.8371 31.9244 20.8371 31.2143C20.8371 23.6401 14.697 17.5 7.1228 17.5H1.43561Z" />
        <path d="M36.5513 17.5C28.9771 17.5 22.837 23.6401 22.837 31.2143C22.837 31.9244 23.4127 32.5 24.1227 32.5H27.5028C35.722 32.5 42.3962 26.6938 43.6556 19.0879C43.7971 18.2336 43.1044 17.5 42.2384 17.5H36.5513Z" />
        <path d="M42.2384 15.5C43.1044 15.5 43.7971 14.7664 43.6556 13.9121C42.3962 6.30615 35.722 0.5 27.5028 0.5H24.1227C23.4127 0.5 22.837 1.07563 22.837 1.78571C22.837 9.35991 28.9771 15.5 36.5513 15.5H42.2384Z" />
      </svg>
    } @else {
      <svg viewBox="0 0 26 26" fill="currentColor" focusable="false" aria-hidden="true">
        <circle cx="3.8696" cy="3.69865" r="3.07273" opacity=".2" />
        <circle cx="13.0879" cy="3.69865" r="3.07273" opacity=".2" />
        <circle cx="22.1919" cy="3.69865" r="3.07273" opacity=".2" />
        <circle cx="3.8696" cy="12.8599" r="3.07273" />
        <circle cx="13.0879" cy="12.8599" r="3.07273" />
        <circle cx="22.1919" cy="12.8599" r="3.07273" />
        <circle cx="3.8696" cy="22.1919" r="3.07273" opacity=".2" />
        <circle cx="13.0879" cy="22.1919" r="3.07273" />
        <circle cx="22.1919" cy="22.1919" r="3.07273" opacity=".2" />
      </svg>
    }`,
  styles:[`:host{display:inline-flex;width:1em;height:1em;flex:0 0 auto;align-items:center;justify-content:center}
    svg{display:block;width:100%;height:100%;overflow:visible}`],
  changeDetection:ChangeDetectionStrategy.OnPush})
export class BrandMark { @Input() brand:Brand='tailscale'; }
