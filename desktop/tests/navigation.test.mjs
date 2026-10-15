import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {categoryPages,categoryForPage} from '../src/navigation.ts';

test('persistent category roots, exclusive tabs and bottom-left About replace the flat rail',()=>{
  const main=readFileSync(new URL('../src/main.ts',import.meta.url),'utf8');
  assert.match(main,/id="category-tailscale"/);
  assert.match(main,/id="nav-3"[^>]*[\s\S]*?selectCategory\('controld'\)/);
  assert.match(main,/categoryPages\(\)/);
  assert.match(main,/id="nav-about"/);
  assert.doesNotMatch(main,/<span class="rail-bottom"[^>]*>READ/);
  assert.ok(existsSync(new URL('../src/connectivity.ts',import.meta.url)),'Custom Tailscale main page is missing');
});

test('every existing page belongs to exactly one category, while About is global',()=>{
  const pages=Object.values(categoryPages).flat().map(item=>item.page);
  assert.equal(new Set(pages).size,pages.length);
  for(const page of ['Overview','Applications','Activity','Sources & health','Settings'])assert.equal(categoryForPage(page),'analytics');
  for(const page of ['Connection','Preferences','DNS resolver'])assert.equal(categoryForPage(page),'tailscale');
  for(const page of ['Control D','Control D policy'])assert.equal(categoryForPage(page),'controld');
  assert.equal(categoryForPage('About'),null);
});
