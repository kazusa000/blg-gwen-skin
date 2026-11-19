// Compare the source BINs with the exact entries in the installed champion WAD.
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const crypto = require('node:crypto');
const wad = fs.readFileSync(process.argv[2]);
const stock = process.argv[3];
const index = new Map();
if (wad.toString('ascii', 0, 2) !== 'RW' || wad[2] !== 3) throw Error('Expected WAD v3');
for (let i = 0; i < wad.readUInt32LE(268); i++) {
  const offset = 272 + i * 32;
  index.set(wad.readBigUInt64LE(offset).toString(16).padStart(16,'0'), offset);
}
let table;
function read(key) {
  const at = index.get(key);
  if (at === undefined) throw Error('Missing WAD entry ' + key);
  const start = wad.readUInt32LE(at + 8), length = wad.readUInt32LE(at + 12);
  const packed = wad.subarray(start, start + length), mode = wad[at + 20];
  let result;
  if ((mode & 15) === 0) result = packed;
  else if ((mode & 15) === 3) result = zlib.zstdDecompressSync(packed);
  else if ((mode & 15) === 4 && table) {
    const chunks = [];
    let pos = 0;
    for (let i = 0; i < (mode >> 4); i++) {
      const k = 16 * (wad.readUInt16LE(at + 22) + i);
      const n = table.readUInt32LE(k), raw = table.readUInt32LE(k + 4);
      const chunk = packed.subarray(pos, pos + n);
      chunks.push(n === raw ? chunk : zlib.zstdDecompressSync(chunk));
      pos += n;
    }
    if (pos !== length) throw Error('Subchunk size mismatch');
    result = Buffer.concat(chunks);
  } else throw Error('Unrecognized WAD codec ' + mode);
  if (result.length !== wad.readUInt32LE(at + 16)) throw Error('Unpacked size mismatch');
  return result;
}
table = read('ce9047d5e4f512c5');
const report = {};
for (const [name, key] of [['skin0.bin','860dd54aee07bfd8'],['animation-skin0.bin','69bcfd01b60a91a1']]) {
  const bytes = read(key);
  if (!bytes.equals(fs.readFileSync(path.join(stock, name)))) throw Error('Installed game source changed: ' + name);
  report[name] = crypto.createHash('sha256').update(bytes).digest('hex');
}
process.stdout.write(JSON.stringify(report));
// Optionally export the direct skin links to inspect cross-skin effect routing.
if(process.argv[4]) {
  const dest=process.argv[4];
  const expected=JSON.parse(fs.readFileSync(path.join(dest,'stock-skin.json'),'utf8')).links.map(p=>p.toLowerCase());
  const hashlist=fs.readFileSync(process.argv[5],'utf8');
  for(let i=0;i<expected.length;i++) {
    const at=hashlist.indexOf(' '+expected[i]+'\n');
    const win=at<0?hashlist.indexOf(' '+expected[i]+'\r\n'):at;
    if(win<16) throw Error('Unresolved linked BIN '+expected[i]);
    const key=hashlist.slice(win-16,win);
    fs.writeFileSync(path.join(dest,'linked-'+i+'.bin'),read(key));
  }
}
