import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

test('recent DNS is the primary incident panel before policy navigation and rule editing',()=>{
  const template=readFileSync(new URL('../src/control-d-management.ts',import.meta.url),'utf8');
  const binding=template.indexOf('id="management-binding"');
  const recent=template.indexOf('id="management-recent"');
  const tabs=template.indexOf('class="incident-tabs"');
  const policy=template.indexOf('id="management-policy"');
  assert.ok(binding>=0&&recent>binding&&tabs>recent&&policy>tabs,
    'Required order: compact endpoint context, recent DNS, policy tabs/editor');
  assert.match(template,/id="incident-dns-search"/);
  assert.match(template,/Follow recent activity/);
  assert.match(template,/Decision \/ reason/);
  assert.match(template,/id="management-confirm"/);
});
