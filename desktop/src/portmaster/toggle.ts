// SPDX-License-Identifier: GPL-3.0-only
// Adapted from Safing @safing/ui toggle-switch (controller, template and SCSS).
// See ../../NOTICE.md. Native checkbox retains keyboard/AT semantics.
import {CommonModule} from '@angular/common';
import {Component, ChangeDetectorRef, forwardRef, Input, ChangeDetectionStrategy} from '@angular/core';
import {ControlValueAccessor, NG_VALUE_ACCESSOR} from '@angular/forms';
@Component({selector:'sfng-toggle',standalone:true,imports:[CommonModule],
  template:`<label><input type="checkbox" [attr.id]="controlId" [attr.aria-label]="name"
    [checked]="value" (change)="onValueChange($event)" (blur)="onTouch()" [disabled]="disabled">
    <span class="slider"><span class="dot" [class.checked]="value && !disabled" [class.disabled]="disabled">
      <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" *ngIf="value && !disabled">
        <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
      <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" *ngIf="!value && !disabled">
        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
      <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" *ngIf="disabled">
        <path d="M5 10a1 1 0 011-1h8a1 1 0 110 2H6a1 1 0 01-1-1z"/></svg>
    </span></span></label>`,
  styles:[`:host{display:flex;align-items:center}label{display:inline-block;width:40px;height:20px;
    position:relative;background:var(--button-light);border-radius:999px}input{position:absolute;width:40px;height:20px;
    inset:0;opacity:0;margin:0;z-index:1;cursor:pointer}input:focus-visible+.slider{outline:2px solid var(--info-blue);
    outline-offset:4px}.slider{position:absolute;inset:0;background:var(--switch-off);border-radius:999px;box-shadow:inset 0 2px 4px #0003;
    transition:background-color .1s}.dot{position:absolute;display:flex;align-items:center;justify-content:center;
    transition:transform .2s;border-radius:50%;background:var(--switch-dot);height:18px;width:18px;bottom:1px;left:1px;color:var(--selection)}
    input:checked:not(:disabled)+.slider{background:var(--selection)}input:disabled{cursor:not-allowed}
    input:disabled+.slider{opacity:.75}.dot.checked{transform:translateX(20px)}.dot.disabled{transform:translateX(10px)}
    svg{width:12px;height:12px}@media(prefers-reduced-motion:reduce){.dot,.slider{transition:none}}`],
  changeDetection:ChangeDetectionStrategy.OnPush,
  providers:[{provide:NG_VALUE_ACCESSOR,useExisting:forwardRef(()=>SfngToggleSwitchComponent),multi:true}]})
export class SfngToggleSwitchComponent implements ControlValueAccessor {
  @Input() name = ''; @Input() controlId = ''; value = false; disabled = false;
  constructor(private detector:ChangeDetectorRef) {}
  writeValue(value:boolean){this.value=value;this.detector.markForCheck()}
  setDisabledState(value:boolean){this.disabled=value;this.detector.markForCheck()}
  onValueChange(event:Event){this.value=(event.target as HTMLInputElement).checked;this.onChange(this.value)}
  onChange=(_:boolean)=>{}; onTouch=()=>{};
  registerOnChange(fn:(value:boolean)=>void){this.onChange=fn}
  registerOnTouched(fn:()=>void){this.onTouch=fn}
}
