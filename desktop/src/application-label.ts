// SPDX-License-Identifier: GPL-3.0-only
// Presentation only: never use the basename as an application identity.
export function applicationName(path:string|null|undefined):string {
  if(!path)return 'Unknown executable';
  return path.split(/[\\/]/).filter(Boolean).at(-1)||path;
}
