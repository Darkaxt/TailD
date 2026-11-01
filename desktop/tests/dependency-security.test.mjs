import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {createRequire} from 'node:module';

const require=createRequire(import.meta.url);
const cacache=require('cacache');
const PackageJson=require('@npmcli/package-json');
async function fixture(){
  // Caller-owned build/test output; its exact workflow cleans these small fixtures.
  const root=process.env.TAILD_PACKAGE_TEST_OUTPUT||tmpdir();
  await mkdir(root,{recursive:true});
  return mkdtemp(join(root,'taild dependency-'));
}

test('patched glob preserves cacache content verification and retrieval',async()=>{
  const cache=await fixture(),bytes=Buffer.from('TailD security maintenance control');
  await cacache.put(cache,'a key with spaces',bytes);
  const result=await cacache.verify(cache);
  assert.equal(result.badContentCount,0);
  assert.equal(result.verifiedContent,1);
  assert.deepEqual((await cacache.get(cache,'a key with spaces')).data,bytes);
});

test('patched glob preserves package-json README discovery in a directory with spaces',async()=>{
  const directory=await fixture(),readme='TailD legitimate package README';
  await writeFile(join(directory,'package.json'),JSON.stringify({name:'taild-security-control',version:'1.0.0'}));
  await writeFile(join(directory,'README.md'),readme);
  const packageJson=await PackageJson.prepare(directory,{steps:['readme']});
  assert.equal(packageJson.content.readme,readme);
  assert.equal(packageJson.content.readmeFilename,'README.md');
});
