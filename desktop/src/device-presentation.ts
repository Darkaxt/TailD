// SPDX-License-Identifier: GPL-3.0-only
export function relativeSeen(value:string|null,online:boolean|null,now=Date.now()):string {
  if(online===true)return 'Online now';
  if(!value||!Number.isFinite(Date.parse(value)))return 'Not reported';
  const seconds=Math.floor((now-Date.parse(value))/1000);
  if(seconds<0)return 'Clock ahead';
  if(seconds<60)return 'Just now';
  if(seconds<3600)return Math.floor(seconds/60)+'m ago';
  if(seconds<48*3600)return Math.floor(seconds/3600)+'h ago';
  const days=Math.floor(seconds/86400);
  if(days<30)return days+' days ago';
  const months=Math.floor(days/30);
  if(days<365)return months+(months===1?' month ago':' months ago');
  const years=Math.floor(days/365);return years+(years===1?' year ago':' years ago');
}
// Small monochrome platform silhouettes; labels remain available to assistive technology.
export function osSymbol(value:string|null):{name:string;path:string} {
  const os=value?.toLowerCase()||'';
  if(os.includes('windows'))return {name:'Windows',path:'M3 4l8-1v8H3zm10-1 8-1v9h-8zM3 13h8v8l-8-1zm10 0h8v9l-8-1z'};
  if(['android'].includes(os))return {name:'Android',path:'m7 5-2-3 1-1 2 3a10 10 0 0 1 8 0l2-3 1 1-2 3a9 9 0 0 1 5 8H2a9 9 0 0 1 5-8ZM7 8v2h2V8Zm8 0v2h2V8ZM4 15h16v5H4Z'};
  if(['macos','darwin','ios','ipados'].includes(os))return {name:value||'Apple',path:'M16 2c0 3-2 5-5 5 0-3 2-5 5-5Zm4 7c-4 2-4 7 0 9-1 3-3 5-5 4l-3-1-3 1c-4 1-8-9-5-13 2-3 4-3 8-1 3-2 5-2 8 1Z'};
  if(os.includes('linux'))return {name:'Linux',path:'M9 3c2-3 7-1 7 3v4c1 3 4 5 4 9l-4 2-4-1-4 1-5-2c0-4 4-6 4-9V6c0-1 0-2 2-3Zm1 4v2h1V7Zm4 0v2h1V7Zm-3 3-2 2 4 1 3-2-3-1Zm-1 4-3 4 5 1 4-1-2-4Z'};
  return {name:value||'OS not reported',path:'M3 3h18v14H3V3Zm2 2v10h14V5H5Zm5 13h4v2h4v2H6v-2h4v-2Z'};
}
