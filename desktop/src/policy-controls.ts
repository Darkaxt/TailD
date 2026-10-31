// SPDX-License-Identifier: GPL-3.0-only
type PolicyRow=Record<string,any>;
export interface FilterChoice {id:string;label:string;enabled:boolean|null}
export function filterChoices(filter:PolicyRow):FilterChoice[]{
  const choices=new Map<string,string>();
  if(typeof filter.PK==='string')choices.set(filter.PK,filter.name||filter.PK);
  for(const level of Array.isArray(filter.levels)?filter.levels:[]){
    if(typeof level.name==='string')choices.set(level.name,level.title||level.name);
  }
  const active=filter.action?.lvl||filter.PK;
  const known=(filter.status===0||filter.status===1)&&(filter.status===0||choices.has(active));
  return [...choices].map(([id,label])=>({id,label,enabled:known?filter.status===1&&id===active:null}));
}
export function optionEnabled(option:PolicyRow):boolean|null {
  if(option.value===1||option.value==='1')return true;
  if(option.value===0||option.value==='0')return false;
  return null;
}
export function filterAction(filter:PolicyRow):{id:string;status:number;label:string;disabled:boolean}{
  const choices=filterChoices(filter),active=filter.action?.lvl||filter.PK;
  if(!choices.length||choices.some(c=>c.enabled===null))return {id:active,status:0,label:'State unavailable',disabled:true};
  const selected=choices.length===1?choices[0].id:filter.selected;
  if(filter.status===1&&(!selected||selected===active))return {id:active,status:0,label:'Disable',disabled:false};
  if(choices.some(c=>c.id===selected))return {id:selected,status:1,label:filter.status===1?'Apply level':'Enable',disabled:false};
  return {id:active,status:1,label:'Enable',disabled:true};
}
