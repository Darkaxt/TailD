// SPDX-License-Identifier: GPL-3.0-only
export type Category='tailscale'|'controld'|'analytics';
export type Page='Connection'|'Preferences'|'DNS resolver'|'Tailscale activity'|'TailDrop'|'Overview'|'App domains'|'Applications'|'Activity'|'Control D'|'Control D policy'|'Sources & health'|'Settings'|'About';
export const categoryPages:Record<Category,{page:Page;label:string;id:string}[]>={
  tailscale:[{page:'Connection',label:'Connection',id:'nav-connection'},
    {page:'Preferences',label:'Preferences',id:'nav-preferences'},{page:'DNS resolver',label:'DNS resolver',id:'nav-resolver'},
    {page:'Tailscale activity',label:'Activity',id:'nav-tailscale-activity'},
    {page:'TailDrop',label:'TailDrop',id:'nav-taildrop'}],
  controld:[{page:'Control D',label:'Recent DNS',id:'nav-recent-dns'},
    {page:'Control D policy',label:'Profile policy',id:'nav-policy'}],
  analytics:[{page:'Overview',label:'Overview',id:'nav-0'},{page:'App domains',label:'Applications',id:'nav-app-domains'},{page:'Applications',label:'Traffic analytics',id:'nav-1'},
    {page:'Activity',label:'Activity',id:'nav-2'},{page:'Sources & health',label:'Sources & health',id:'nav-4'},
    {page:'Settings',label:'Collection settings',id:'nav-5'}]};
export function categoryForPage(page:Page):Category|null {
  return (Object.keys(categoryPages) as Category[]).find(key=>categoryPages[key].some(item=>item.page===page))||null;
}
