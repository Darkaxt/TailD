import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';

const read=name=>readFileSync(new URL('../src/'+name,import.meta.url),'utf8');

test('category marks keep equal optical padding in unchanged navigation hit targets',()=>{
  const css=read('styles.css');
  assert.match(css,/\.nav-link>svg,\.nav-link>taild-brand-mark\{width:22px;height:22px/);
  assert.ok(!/\.rail \.category-root:first-child taild-brand-mark\{width:28px/.test(css),'Tailscale uses a larger icon box');
});

test('navigation and product headers use bundled marks, not TD or the generic provider icon',()=>{
  const main=read('main.ts');
  assert.doesNotMatch(main,/>TD<\/span>/);
  assert.match(main,/id="nav-3"[\s\S]*?<taild-brand-mark brand="controld"/);
  assert.match(main,/id="category-tailscale"[^>]*>[\s\S]*?<taild-brand-mark brand="tailscale"/);
  assert.match(main,/class="eyebrow product-brand"[^>]*><taild-brand-mark brand="tailscale"/);
  assert.match(main,/[Ii]ndependent TailDNS fork/);
});

test('provider panel headings and source banners share the reviewed Control D artwork',()=>{
  assert.match(read('control-d-management.ts'),/id="management-binding" class="incident-header-controls"/);
  assert.match(read('control-d-management.ts'),/label="Recent DNS · incident resolutions" brand="controld"/);
  assert.match(read('collection.ts'),/label="Control D binding · read only" brand="controld"/);
  assert.match(read('ingestion-notice.ts'),/<taild-brand-mark brand="controld" \*ngIf="source.kind==='dns'"/);
  assert.match(read('portmaster/panel.ts'),/<h2>@if\(brand\)\{<taild-brand-mark/);
});

test('brand geometry is static and decorative without weakening the native content policy',()=>{
  const path=new URL('../src/brand-mark.ts',import.meta.url);
  assert.ok(existsSync(path),'shared bundled brand artwork is missing');
  const artwork=read('brand-mark.ts');
  assert.match(artwork,/'aria-hidden':'true'/);
  assert.match(artwork,/viewBox="0 0 44 33"/);
  assert.match(artwork,/viewBox="0 0 26 26"/);
  assert.equal((artwork.match(/<circle /g)||[]).length,9);
  assert.doesNotMatch(artwork,/innerHTML|<script|<image|<rect|href=|url\(/);
  const native=readFileSync(new URL('../native/Program.cs',import.meta.url),'utf8');
  assert.match(native,/connect-src 'none'; img-src 'self'/);
});
