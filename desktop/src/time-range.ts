/** Rolling presets use elapsed UTC time; Today retains local calendar semantics. */
export const DEFAULT_TIME_RANGE='week';
export function presetBounds(range:string,now=new Date()):{start:string;end:string}{
  const duration=range==='week'?7*86400000:range==='hour'?3600000:900000;
  const from=range==='today'?new Date(now.getFullYear(),now.getMonth(),now.getDate()):new Date(now.getTime()-duration);
  return {start:from.toISOString(),end:now.toISOString()};
}
export function utcTickPattern(start:string,end:string):string{
  return Date.parse(end)-Date.parse(start)>=86400000?'%b %d':'%H:%M';
}
