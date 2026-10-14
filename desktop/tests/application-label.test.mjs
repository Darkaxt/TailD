import test from 'node:test';
import assert from 'node:assert/strict';
import {applicationName} from '../src/application-label.ts';

test('display names shorten Windows and POSIX paths without changing identity',()=>{
  const paths=['C:\\First\\browser.exe','D:\\Second\\browser.exe'];
  assert.deepEqual(paths.map(applicationName),['browser.exe','browser.exe']);
  assert.notEqual(paths[0],paths[1]);
  assert.equal(applicationName('/usr/bin/browser'),'browser');
  assert.equal(applicationName(null),'Unknown executable');
  assert.equal(applicationName('=literal <img>.exe'),'=literal <img>.exe');
});
