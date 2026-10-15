// SPDX-License-Identifier: GPL-3.0-only
type Value=Record<string,any>;
export function resolutionReason(row:Value,filters:Value[]=[],services:Value[]=[]):string{
  const raw=row.fact?.raw||{},trigger=row.reason||raw.trigger,value=row.reason_value||raw.triggerValue;
  if(!trigger)return row.outcome==='block'?'Blocking reason unavailable':'Decision reason unavailable';
  const labels:Record<string,string>={filter:'Filter / list',service:'Service',custom:'Custom rule',grule:'Global rule',default:'Profile default',rebind:'Rebind protection'};
  const label=labels[trigger]||String(trigger);
  if(!value)return ['filter','service','custom','grule'].includes(trigger)?label+' · name not supplied':label;
  const collection=trigger==='filter'?filters:trigger==='service'?services:[];
  const match=collection.find(item=>item.PK===value||item.levels?.some((level:Value)=>level.name===value));
  const name=match?.name;
  return label+' · '+(name&&name!==value?name+' ('+value+')':String(value));
}
export function resolutionCategories(row:Value):string[]{
  let categories=row.fact?.raw?.categories;
  if(typeof categories==='string'){
    try{categories=JSON.parse(categories)}catch{return categories.trim()?[categories]:[]}
  }
  if(!Array.isArray(categories))return [];
  return [...new Set(categories.slice(0,64).map(item=>typeof item==='string'?item:typeof item?.categoryName==='string'?item.categoryName:
    typeof item?.categoryId==='string'?'Category '+item.categoryId:'').filter(Boolean))] as string[];
}
