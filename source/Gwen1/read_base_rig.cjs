// Read only the base-skin mesh, skeleton, and animation clips referenced by the local Gwen package.
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const wad = fs.readFileSync(process.argv[2]);
const out = path.join(__dirname, 'rig-study');
fs.mkdirSync(out, {recursive:true});
const U = value => BigInt.asUintN(64,value);
const rot = (v,r) => U((v<<r)|(v>>(64n-r)));
const [p1,p2,p3,p4,p5] = [11400714785074694791n,14029467366897019727n,1609587929392839161n,9650029242287828579n,2870177450012600261n];
const round = (a,v) => U(rot(U(a+v*p2),31n)*p1);
function hash(name) {
    const b=Buffer.from(name.toLowerCase()); let i=0, h=p5;
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
if(hash('')!==0xef46db3751d8e999n || hash('data/characters/ziggs/skins/skin0.bin')!==0x7d48fa11c2364200n) throw Error('Path hash check failed');
const dir=new Map();
for(let i=0;i<wad.readUInt32LE(268);i++){const k=272+i*32;dir.set(wad.readBigUInt64LE(k),k);}
let table;
function read(name) {
    const k=dir.get(hash(name));if(k===undefined)return;
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
    else throw Error(name+' compression '+mode);
    if(data.length!==raw)throw Error('Length mismatch '+name);
    return data;
}
for(const name of ['data/final/champions/gwen.wad.subchunktoc','data/final/champions/gwen.subchunktoc','data/final/champions/gwen.wad.client.subchunktoc']) {
    table=read(name);if(table)break;
}
const entries={};
function readConfig(name) {
    const b=read(name);if(!b)throw Error('Missing '+name);
    if (name.includes('/animations/')) fs.writeFileSync(path.join(out,'animation-skin0.bin'),b);
    return [...new Set(b.toString('latin1').match(/(?:assets|data)\/characters\/gwen\/[a-z0-9_./-]+?\.(?:skl|skn|anm)\b/gi) || [])];
}
const names=[...readConfig('data/characters/gwen/skins/skin0.bin'),...readConfig('data/characters/gwen/animations/skin0.bin')];
const graph=fs.readFileSync(path.join(out,'animation-skin0.bin'));
const motions=['idle','run','attack','spell','recall','dance','joke','taunt','laugh','crit','death','respawn','walk','run_fast','channel','idle_in','recall_windup','emote','spell1_cast','spell1_loop','spell1_end','idle_injured'];
for (const stem of motions) for (const suffix of ['', '1','2','3','4','01','02','03','04','_in','_loop','_out','_a','_b','_windup','_inplace']) {
    for(const prefix of ['gwen_base_','gwen_','']) {
        const n='assets/characters/gwen/skins/base/animations/'+prefix+stem+suffix+'.anm';
        const h=hash(n);if(!dir.has(h))continue;
        const id=Buffer.alloc(8);id.writeBigUInt64LE(h);
        if(graph.includes(id))names.push(n);
    }
}
for(const name of names) {
    const data=read(name);if(!data)continue;
    const key=path.basename(name).toLowerCase();
    if(entries[key] && entries[key]!==name)throw Error('Name collision '+name);
    entries[key]=name;
    fs.writeFileSync(path.join(out,key),data);
}
fs.writeFileSync(path.join(out,'entries.json'),JSON.stringify(entries,null,2));
console.log(Object.keys(entries).join(' '));
