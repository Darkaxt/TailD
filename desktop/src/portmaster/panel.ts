// SPDX-License-Identifier: GPL-3.0-only
// Adapted from Safing Portmaster DashboardWidgetComponent. See ../../NOTICE.md.
import {Component, Input, ChangeDetectionStrategy} from '@angular/core';
import {Brand,BrandMark} from '../brand-mark';
@Component({selector: 'app-dashboard-widget', standalone: true,
  imports:[BrandMark],
  template: '<h2>@if(brand){<taild-brand-mark [brand]="brand" />}{{label}}</h2><ng-content />',
  styles: [`:host{background:var(--cards-secondary);padding:16px;align-self:stretch;border-radius:6px;
    display:flex;flex-direction:column;gap:8px}h2{font-size:12px;text-transform:uppercase;
    color:var(--text-secondary);font-weight:400;display:flex;align-items:center;gap:8px;
    padding-bottom:8px;margin:0}`], changeDetection: ChangeDetectionStrategy.OnPush})
export class DashboardWidgetComponent { @Input() label = ''; @Input() brand:Brand|null=null; }
