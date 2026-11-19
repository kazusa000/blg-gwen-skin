const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const cup = process.argv.includes('--worlds-cup');
const champion = cup ? 'Aphelios' : 'Gwen';
const wadPath = path.join(process.env.GWEN_GAME || 'C:/Riot Games/League of Legends/Game',
                          'DATA/FINAL/Champions',champion+'.wad.client');
const out = path.join(__dirname, 'stock');
fs.mkdirSync(out, { recursive: true });
const wad = fs.readFileSync(wadPath);
const U = v => BigInt.asUintN(64,v);
const rot = (v,r) => U((v<<r)|(v>>(64n-r)));
const [p1,p2,p3,p4,p5] = [11400714785074694791n,14029467366897019727n,1609587929392839161n,9650029242287828579n,2870177450012600261n];
const round = (a,v) => U(rot(U(a+v*p2),31n)*p1);
function hash(name) {
  const b = Buffer.from(name.toLowerCase()); let i=0, h=p5;
  if (b.length>=32) {
    let v=[U(p1+p2),p2,0n,U(-p1)];
    while(i+32<=b.length) for(let j=0;j<4;j++,i+=8) v[j]=round(v[j],b.readBigUInt64LE(i));
    h=U(v.reduce((a,s,j)=>a+rot(s,[1n,7n,12n,18n][j]),0n));
    for(const s of v) h=U((h^round(0n,s))*p1+p4);
  }
  h=U(h+BigInt(b.length));
  while(i+8<=b.length){h=U(rot(h^round(0n,b.readBigUInt64LE(i)),27n)*p1+p4);i+=8;}
  if(i+4<=b.length){h=U(rot(h^U(BigInt(b.readUInt32LE(i))*p1),23n)*p2+p3);i+=4;}
  while(i<b.length){h=U(rot(h^U(BigInt(b[i++])*p5),11n)*p1);}
  h=U((h^(h>>33n))*p2);h=U((h^(h>>29n))*p3);return h^(h>>32n);
}
const dir=new Map();
for(let i=0;i<wad.readUInt32LE(268);i++){const k=272+i*32;dir.set(wad.readBigUInt64LE(k),k);}
let table;
function read(name) {
  const k=dir.get(hash(name));if(k===undefined)throw new Error('Not in WAD: '+name);
  const offset=wad.readUInt32LE(k+8),len=wad.readUInt32LE(k+12),raw=wad.readUInt32LE(k+16);
  const mode=wad[k+20],b=wad.subarray(offset,offset+len);let data;
  if((mode&15)===0)data=b;
  else if((mode&15)===3)data=zlib.zstdDecompressSync(b);
  else if((mode&15)===4 && table) {
    let pos=0;const chunks=[];
    for(let j=0;j<(mode>>4);j++) {
      const t=(wad.readUInt16LE(k+22)+j)*16;
      const count=table.readUInt32LE(t),size=table.readUInt32LE(t+4);
      const chunk=b.subarray(pos,pos+count);chunks.push(count===size?chunk:zlib.zstdDecompressSync(chunk));pos+=count;
    }
    data=Buffer.concat(chunks);
  } else if((mode&15)===4)data=zlib.zstdDecompressSync(b);
  else throw new Error(name+' compression '+mode);
  if(data.length!==raw)throw new Error('Length mismatch '+name);
  return data;
}
table=read('data/final/champions/'+champion.toLowerCase()+'.wad.subchunktoc');
if (cup) {
  for (const file of ['aphelios_skin18.skn','aphelios_skin18_summonerscup_tx_cm.tex']) {
    fs.writeFileSync(path.join(out,file),read('assets/characters/aphelios/skins/skin18/'+file));
  }
  return;
}
if (process.argv.includes('--needlework')) {
  for (const stem of ['NeedleMesh','WindupMesh01','WindupMesh02','WindupMesh03']) {
    const file='Gwen_Base_R_'+stem+'.scb';
    fs.writeFileSync(path.join(out,file),read('assets/characters/gwen/skins/base/particles/'+file));
  }
  return;
}
for (const file of [
  'Gwen_Base_W_OuteredgeMesh001.scb',
  'Gwen_Base_W_RingMesh01.scb',
  'Gwen_Base_W_BirthCastMeshWeaving01.scb',
  'Gwen_Base_W_BirthStrandsmesh.scb',
  'Generic_WIndicator_Corner_FirstNew.tex',
  'Generic_WIndicator_Corner_FirstNew_Overlay.tex',
  'Generic_GroundBaseLayer.tex',
  'Generic_GlowSoft.tex',
  'Generic_TrailCigSmoke_Connected_Second.tex',
  'Generic_RibbonMask01.tex',
  'Gwen_Base_Q_ATK01_OPEN.scb',
  'Gwen_Base_Q_ATK01_CLOSE.scb',
  'Q_MeshTrail01.tex',
  'Q_MeshTrail02.tex',
  'Draven_Base_W_Color-hold.tex',
]) {
  const name='assets/characters/gwen/skins/base/particles/'+file.toLowerCase();
  const data=read(name);
  fs.writeFileSync(path.join(out,file),data);
  process.stdout.write(file+' '+data.length+'\n');
}
