// Read a compiled package using its exact game paths, retaining all non-character resources.
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const {pathHash} = require('../vfx/check_import.cjs');
const [input, namesFile, directory] = process.argv.slice(2);
const bytes = fs.readFileSync(input);
const assets = JSON.parse(fs.readFileSync(namesFile, 'utf8'));
const keys = new Map(assets.map(name => [pathHash(name),name]));
const size = bytes.readUInt32LE(268);
if (size !== keys.size || bytes.toString('ascii',0,2) !== 'RW' || bytes[2] !== 3) throw Error('Unexpected WAD table');
for (let i=0; i<size; i++) {
  const at=272+32*i, key=bytes.readBigUInt64LE(at), name=keys.get(key);
  if (!name || name.includes('..') || !/^(data|assets)\//.test(name)) throw Error('Unexpected asset path');
  keys.delete(key);
  const start=bytes.readUInt32LE(at+8), length=bytes.readUInt32LE(at+12);
  const source=bytes.subarray(start,start+length), codec=bytes[at+20]&15;
  if (![0,3].includes(codec)) throw Error('Unexpected WAD codec');
  const raw=codec===3 ? zlib.zstdDecompressSync(source) : source;
  if (raw.length!==bytes.readUInt32LE(at+16)) throw Error('Invalid raw size');
  const output=path.join(directory,name);
  fs.mkdirSync(path.dirname(output),{recursive:true});
  fs.writeFileSync(output,raw);
}
if (keys.size) throw Error('Incomplete WAD');

