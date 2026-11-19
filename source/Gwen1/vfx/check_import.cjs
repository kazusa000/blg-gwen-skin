// Verify the game path and bytes of every entry produced by the external importer.
const fs = require('node:fs');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const u64 = x => BigInt.asUintN(64,x);
const rot = (x,n) => u64((x<<n)|(x>>(64n-n)));
const p1=11400714785074694791n, p2=14029467366897019727n, p3=1609587929392839161n;
const p4=9650029242287828579n, p5=2870177450012600261n;
const lane=(v,k)=>u64(rot(u64(v+k*p2),31n)*p1);
function pathHash(name) {
  const b=Buffer.from(name.toLowerCase());
  let h=p5, i=0;
  if(b.length>=32) {
    const lanes=[u64(p1+p2),p2,0n,u64(-p1)];
    while(i+32<=b.length) {
      for(let j=0;j<4;j++,i+=8) lanes[j]=lane(lanes[j],b.readBigUInt64LE(i));
    }
    h=u64(lanes.reduce((t,v,j)=>t+rot(v,[1n,7n,12n,18n][j]),0n));
    for(const v of lanes) h=u64((h^lane(0n,v))*p1+p4);
  }
  h=u64(h+BigInt(b.length));
  while(i+8<=b.length) {h=u64(rot(h^lane(0n,b.readBigUInt64LE(i)),27n)*p1+p4);i+=8;}
  if(i+4<=b.length) {h=u64(rot(h^u64(BigInt(b.readUInt32LE(i))*p1),23n)*p2+p3);i+=4;}
  while(i<b.length) h=u64(rot(h^u64(BigInt(b[i++])*p5),11n)*p1);
  h=u64((h^(h>>33n))*p2);h=u64((h^(h>>29n))*p3);
  return h^(h>>32n);
}
module.exports = {pathHash};
if (require.main === module) {
if(pathHash('data/characters/gwen/skins/skin0.bin')!==0x860dd54aee07bfd8n) throw Error('Gwen WAD key mismatch');
const report=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const wad=fs.readFileSync(process.argv[3]);
const expected=new Map(Object.entries(report.assetSha256).map(([name,sha])=>[pathHash(name),{name,sha}]));
if(wad.toString('ascii',0,2)!=='RW'||wad[2]!==3||wad.readUInt32LE(268)!==expected.size) throw Error('Unexpected WAD index');
const seen=[];
for(let i=0;i<wad.readUInt32LE(268);i++) {
  const at=272+i*32,key=wad.readBigUInt64LE(at);
  const target=expected.get(key);
  if(!target||seen.includes(target.name)) throw Error('Incorrect imported path: '+key.toString(16));
  const start=wad.readUInt32LE(at+8),length=wad.readUInt32LE(at+12);
  const codec=wad[at+20]&15, packed=wad.subarray(start,start+length);
  let data;
  if(codec===0) data=packed;
  else if(codec===3) data=zlib.zstdDecompressSync(packed);
  else throw Error('Unsupported importer codec: '+codec);
  if(data.length!==wad.readUInt32LE(at+16)||crypto.createHash('sha256').update(data).digest('hex')!==target.sha) throw Error('Imported bytes differ: '+target.name);
  seen.push(target.name);
}
console.log('Importer round-trip verified',seen.length,'game paths and SHA-256 fingerprints.');
}
