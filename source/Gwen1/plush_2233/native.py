"""Patch only Gwen's Doll section and append two local doll poses to the stock clips."""
import hashlib
import json
import struct
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
from PIL import Image

from atlas import HERE,SKIN,WORK,make_atlas
from model import build_model,part_bone,SCALE,OFFSETS
sys.path.insert(0,str(HERE.parent))
from rig_data import Gwen,_CompressedEvaluator
sys.path.insert(0,str(HERE.parent/'vfx'))
from build_qw import PREFIX,SKIN_BIN,encode_tex,check_tex,read_json

BASE=HERE.parent/'rig-study'
ROOT='assets/characters/gwen/skins/base/'
TEXTURE=ROOT+'blg_2233_doll.tex'
DEST=SKIN/'Gwen1-BLG-QWER-2233.fantome'
CLIPS=('death','respawn','joke_start2','joke_loop','joke_to_run')

def hash_joint(name):
    h=0
    for c in name.lower().encode():
        h=(h<<4)+c
        high=h&0xf0000000
        h=(h^(high>>24))&~high
    return h

def put(buf,off,fmt,*v):
    struct.pack_into('<'+fmt,buf,off,*v)

def src_names(g):
    return [n for n in g.names if 'Doll_' in n and n not in ('Doll_Root','Doll_Main')]

def base_offset(g,num):
    main=g.bind[g.names.index('Doll_Main')]
    dest=main[:3,3]*SCALE+[OFFSETS[num],0,0]
    return np.linalg.solve(main[:3,:3],dest-main[:3,3])

def extend_rig(g):
    old=(BASE/'gwen_base.skl').read_bytes()
    count=len(g.names);joff,lo,io=struct.unpack_from('<III',old,20)
    head=bytearray(old[:joff]); records=bytearray(old[joff:lo])
    lookup=[old[j:j+8] for j in range(lo,io,8)]
    influences=list(g.influences); old_tail=io+len(influences)*2
    tail=bytearray(old[old_tail:])
    joints=list(g.names);parents=list(g.parents); bind=list(g.bind)
    add={}
    for num in (22,33):
        for src in ('Doll_Main',*src_names(g)):
            j=g.names.index(src); anchor=src=='Doll_Main'
            name=part_bone(num,'main' if anchor else src)
            par=g.names.index('Doll_Main') if anchor else add[(num,g.names[g.parents[j]])]
            h=hash_joint(name);idx=len(joints); add[num,src]=idx
            rec=bytearray(old[joff+j*100:joff+(j+1)*100])
            put(rec,2,'Hh',idx,par);put(rec,8,'I',h)
            if anchor:
                put(rec,16,'3f3f4f',*base_offset(g,num),1,1,1,0,0,0,1)
            else:
                put(rec,16,'3f',*(g.local[j,:3,3]*SCALE))
            world=g.bind[j].copy();world[:3,3]=world[:3,3]*SCALE+[OFFSETS[num],0,0]
            put(rec,56,'3f',*np.linalg.inv(world)[:3,3])
            records.extend(rec); joints.append(name);bind.append(world);parents.append(par);influences.append(idx)
            lookup.append(struct.pack('<HHI',idx,0,h))
    assert len(influences)<=256 and len(set(map(hash_joint,joints)))==len(joints)
    nlo=joff+len(records);nio=nlo+8*len(lookup); ntail=nio+2*len(influences);delta=ntail-old_tail
    for j,name in enumerate(joints):
        at=j*100+96
        if j<count:
            put(records,at,'i',struct.unpack_from('<i',records,at)[0]+delta)
        else:
            nameoff=ntail+len(tail);tail.extend(name.encode()+b'\0')
            tail.extend(bytes(-len(tail)%4));put(records,at,'i',nameoff-(joff+at))
    put(head,14,'HI',len(joints),len(influences));put(head,24,'II',nlo,nio)
    for at in (32,36,40):
        off=struct.unpack_from('<I',head,at)[0]
        if off not in (0,0xffffffff):put(head,at,'I',off+delta)
    data=head+records+b''.join(sorted(lookup,key=lambda r:struct.unpack_from('<I',r,4)[0]))+struct.pack('<'+'H'*len(influences),*influences)+tail
    put(data,0,'I',len(data))
    for j,n in enumerate(joints):
        k=joff+100*j+96;p=k+struct.unpack_from('<i',data,k)[0]
        assert data[p:data.index(0,p)].decode()==n
    return bytes(data),joints,influences,add,parents,np.array(bind)

def vertices(g,model,names,influences):
    p=np.array(model.p);face=np.array(model.tri);uvs=np.array(model.uv);normal=np.zeros_like(p)
    corners=p[face];area=np.cross(corners[:,1]-corners[:,0],corners[:,2]-corners[:,0])
    good=np.linalg.norm(area,axis=1)>1e-8
    for _,label,a,b,i,j in model.parts:
        local=np.zeros((j-i,3))
        for k in range(3):np.add.at(local,face[a:b,k]-i,area[a:b])
        _,inv=np.unique(np.round(p[i:j],5),axis=0,return_inverse=True)
        sums=np.zeros((inv.max()+1,3));np.add.at(sums,inv,local)
        normal[i:j]=sums[inv]
    lengths=np.linalg.norm(normal,axis=1)
    normal/=np.maximum(1e-10,lengths[:,None])
    ids=np.array([influences.index(names.index(b)) for b in model.bones])
    vs=np.zeros(len(p),dtype=g.verts.dtype);vs['p']=p;vs['n']=normal;vs['uv']=uvs;vs['i'][:,0]=ids;vs['w'][:,0]=1
    # Trim duplicate seam/pole records, retaining UV splits and independent joints.
    keep,mapback=np.unique(vs,return_inverse=True)
    tris=mapback[face[good]].astype('<u2')
    assert np.all(np.linalg.norm(keep['n'][np.unique(tris)],axis=1)>.98)
    return keep,tris

def replace_section(g,v,f):
    old=(BASE/'gwen_base.skn').read_bytes();hdr=bytearray(old[:12+len(g.sections)*80+60])
    oi=[];ov=[];ni=nv=0
    for k,(name,(base,vc,first,ic)) in enumerate(g.sections.items()):
        if name=='Doll':mesh,tri=v,f
        else:mesh,tri=g.verts[base:base+vc],g.tri[first//3:(first+ic)//3].astype(int)-base
        assert tri.min()>=0 and tri.max()<len(mesh)
        ov.append(mesh);oi.append(tri+nv)
        put(hdr,12+80*k+64,'4I',nv,len(mesh),ni,tri.size)
        nv+=len(mesh);ni+=tri.size
    assert nv<65536
    k=12+80*len(g.sections);put(hdr,k+4,'II',ni,nv)
    allv=np.concatenate(ov)
    # The stock bounding volume already encloses the replacement geometry.
    lo,hi=np.frombuffer(hdr,'<f4',6,k+20).reshape(2,3)
    assert np.all(v['p']>=lo) and np.all(v['p']<=hi)
    oldend=len(hdr)+g.tri.size*2+len(g.verts)*g.verts.itemsize
    return bytes(hdr)+np.concatenate(oi).astype('<u2').tobytes()+allv.tobytes()+old[oldend:]

def extend_clip(g,key):
    # Copy the compressed control stream, preserving stock timing, interpolation and
    # quaternion bits. New cache entries address the corresponding duplicated keys.
    old=(BASE/(key+'.anm')).read_bytes();assert old[:8]==b'r3d2canm'
    nj,nk,nc=struct.unpack_from('<III',old,24)
    fo,co,ho=[12+x for x in struct.unpack_from('<III',old,116)]
    keys=np.frombuffer(old,'<u2',nk*5,fo).reshape(-1,5)
    hashes=list(np.frombuffer(old,'<u4',nj,ho))
    cache=np.frombuffer(old,'<u2',nc*nj*12,co).reshape(nc,nj,12)
    loT,hiT,loS,hiS=np.frombuffer(old,'<f4',12,68).reshape(4,3)
    def encoded(v,lo,hi):
        val=(np.asarray(v)-lo)/np.maximum(hi-lo,1.e-10)
        assert val.min()>-.001 and val.max()<1.001,(key,v)
        return np.clip(np.rint(val*65535),0,65535).astype('<u2')
    source_indices=[hashes.index(hash_joint(n)) for n in src_names(g)]
    maps={};rows=[];caches=[];extended=list(hashes)
    for num in (22,33):
        root=len(extended);extended.append(hash_joint(part_bone(num,'main')))
        static=[]
        packed=(3<<45)|(16384<<30)|(16384<<15)|16384
        identity=[(packed>>(16*i))&65535 for i in range(3)]
        for channel,val in enumerate((identity,encoded(base_offset(g,num),loT,hiT),encoded([1,1,1],loS,hiS))):
            for time in (0,0,65535,65535):
                static.append(len(rows));rows.append([time,root|(channel<<14),*val])
        caches.append(('static',static))
        for idx in source_indices:
            n=g.names[g.byhash[int(hashes[idx])]]
            maps[num,idx]=len(extended);extended.append(hash_joint(part_bone(num,n)))
            caches.append((num,idx))
    updates=np.zeros((3,nk),np.int64)
    for k,row in enumerate(keys):
        idx=int(row[1])&0x3fff;kind=int(row[1])>>14
        updates[0,k]=len(rows);rows.append(row)
        if idx not in source_indices:continue
        for z,num in enumerate((22,33),1):
            rec=row.copy();rec[1]=maps[num,idx]|(kind<<14)
            if kind==1:
                pos=loT+(hiT-loT)*(row[2:].astype(float)/65535)
                rec[2:]=encoded(pos*SCALE,loT,hiT)
            updates[z,k]=len(rows);rows.append(rec)
    assert len(rows)<65535
    heads=np.zeros((nc,len(extended),12),'<u2')
    def remap(a,ids):
        sentinel=a==65535;return np.where(sentinel,65535,ids[np.where(sentinel,0,a)])
    heads[:,:nj]=remap(cache,updates[0])
    for j,(num,src) in enumerate(caches,nj):
        heads[:,j]=src if num=='static' else remap(cache[:,src],updates[1 if num==22 else 2])
    header=bytearray(old[:fo]);K=np.asarray(rows,'<u2').tobytes()
    newco=fo+len(K);gap=bytes(-newco%4);newco+=len(gap)
    newho=newco+heads.nbytes
    ext=bytes(header)+K+gap+heads.tobytes()+np.array(extended,'<u4').tobytes()
    out=bytearray(ext);put(out,12,'I',len(out)-12);put(out,24,'II',len(extended),len(rows))
    put(out,116,'III',fo-12,newco-12,newho-12)
    # Check native samples and random seeks on both sides of every jump cache.
    orig=_CompressedEvaluator(old,nj);new=_CompressedEvaluator(out,len(extended))
    dur,fps=struct.unpack_from('<ff',old,36)
    for t in list(np.linspace(0,dur,round(dur*fps)+1))+list(np.linspace(dur,0,15)):
        before=orig.evaluate(t);after=new.evaluate(t)
        for a,b in zip(before,after):assert np.allclose(a,b[:nj],atol=1e-6)
        for num in (22,33):
            src=np.array(source_indices);dest=[maps[num,i] for i in src]
            assert np.allclose(after[0][dest],before[0][src]*SCALE,atol=.016)
            for i in (1,2):assert np.allclose(after[i][dest],before[i][src],atol=1e-6)
    return bytes(out)

def main():
    W=make_atlas();g=Gwen();m=build_model()
    skl,names,inf,add,parents,bind=extend_rig(g);v,tri=vertices(g,m,names,inf)
    np.savez_compressed(WORK/'mesh.npz',vertices=v,triangles=tri,names=np.asarray(names),influences=inf,parents=parents,bind=bind)
    assets={ROOT+'gwen_base.skl':skl,ROOT+'gwen_base.skn':replace_section(g,v,tri)}
    tex=encode_tex(W.convert('RGBA'));check_tex(tex,W.convert('RGBA'));assets[TEXTURE]=tex
    paths=json.loads((BASE/'entries.json').read_text('utf8'))
    for key in CLIPS:assets[paths[key+'.anm'].lower()]=extend_clip(g,key)
    with ZipFile(SKIN/'Gwen1-BLG-QWER-v5.fantome') as source,TemporaryDirectory(dir=WORK) as directory:
        t=Path(directory);bin0=source.read(PREFIX+SKIN_BIN)
        old=struct.pack('<Q',0x2dfd93f5b4fd76d8);new=struct.pack('<Q',0xad66b1f33a4b143b)
        assert bin0.count(old)==1
        assets[SKIN_BIN]=bin0.replace(old,new)
        decoded=read_json(assets[SKIN_BIN],t)['objects']
        skin=next(o for o in decoded.values() if 'skinMeshProperties' in o)
        override=next(x for x in skin['skinMeshProperties']['materialOverride'] if x.get('submesh')=='Doll')
        assert override['texture'].lower().endswith('ad66b1f33a4b143b') and skin['skinMeshProperties']['initialSubmeshToHide']=='Needle Doll'
        allassets={n[len(PREFIX):]:source.read(n) for n in source.namelist() if n.startswith(PREFIX)};allassets.update(assets)
        meta=json.loads(source.read('META/info.json'));meta.update(Name='Gwen BLG - 22 and 33 dolls + QWER',Version='0.9.0',Description='Paired 22/33 embroidery dolls for the default Gwen joke, death and respawn actions, with the approved BLG combat visuals.')
        stage=t/DEST.name
        with ZipFile(stage,'w',compression=ZIP_DEFLATED,compresslevel=7) as z:
            z.writestr('META/info.json',json.dumps(meta,ensure_ascii=False,indent=2))
            for name,data in sorted(allassets.items()):z.writestr(PREFIX+name,data)
        with ZipFile(stage) as z:assert z.testzip() is None and all(z.read(PREFIX+k)==v for k,v in allassets.items())
        report={'assetSha256':{k:hashlib.sha256(v).hexdigest() for k,v in allassets.items()}}
        (WORK/'import-check.json').write_text(json.dumps(report))
        stage.replace(DEST)
    print(DEST,len(v),len(tri),'two dolls, five patched clips,',len(allassets),'WAD entries',flush=True)

if __name__=='__main__':main()

