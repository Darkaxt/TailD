// Build-time only. Reuse the pinned Windows topology; no remote map at runtime.
// npm ci in desktop supplies these locked dependencies. Optional argv[2] points
// to another node_modules containing the same d3-geo 3.1.1/topojson-client 3.1.0.
import {readFileSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {resolve, dirname} from 'node:path';
const root=resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const modules=resolve(process.argv[2] || resolve(root,'desktop/node_modules'));
const {geoEquirectangular,geoPath}=await import(pathToFileURL(resolve(modules,'d3-geo/src/index.js')));
const {feature}=await import(pathToFileURL(resolve(modules,'topojson-client/src/index.js')));
const source=readFileSync(resolve(root,'desktop/src/portmaster/world-50m.json'));
const sha=createHash('sha256').update(source).digest('hex');
if(sha!=='c8598aca2a616f5fcdda15a95c5ee2d7c2be4ecc30edf67943c79e5ae97ee6e5') throw Error('Review changed topology/source notices first');
const topology=JSON.parse(source);
const countries=feature(topology,topology.objects.countries);
countries.features=countries.features.filter(c=>c.properties.iso_a2!=='AQ');
const projection=geoEquirectangular().fitExtent([[8,8],[992,492]],countries);
const path=geoPath(projection).digits(2);
const output={schema:1,width:1000,height:500,source_sha256:sha,
  countries:countries.features.map(c=>({code:c.properties.iso_a2,name:c.properties.name,path:path(c)}))};
writeFileSync(resolve(root,'android/src/main/assets/taild-world-map.json'),JSON.stringify(output)+'\n');
console.log(`${output.countries.length} offline country shapes; source ${sha}`);
