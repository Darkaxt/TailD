// SPDX-License-Identifier: GPL-3.0-only
export function availableSources(runtime:{integration_ready?:{traffic?:boolean;dns?:boolean}}|null,
  catalog:{sources:{kind:string}[]}|null){
  const recorded=new Set((catalog?.sources||[]).map(source=>source.kind));
  return {traffic:recorded.has('traffic')||runtime?.integration_ready?.traffic===true,
    dns:recorded.has('dns')||runtime?.integration_ready?.dns===true};
}
