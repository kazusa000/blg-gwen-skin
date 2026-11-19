"""Ship and independently decode the native recall animation, SKN section, rig and BIN events."""
from core import *
import hashlib,json,re,struct,shutil,subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile,ZIP_DEFLATED
from PIL import Image
from build_qw import PREFIX,SKIN_BIN,ANIM_BIN,convert,read_json,keep_untouched,encode_tex,check_tex
from q_effect import _entries,_matching_brace
from rig_data import decode_quat
ROOT='assets/characters/gwen/skins/base/'
PROP_PATH=ROOT+'blg_recall_textile.tex'

def hash_joint(s):
    h=0
    for c in s.lower().encode():
        h=h*16+c;high=h&0xf0000000;h=(h^(high>>24))&~high
    return h

def extend(old,D):
    names=D['names'].tolist();inf=D['inf'];n,oldni,jo,lo,io=struct.unpack_from('<HIIII',old,14)
    assert n==161
    head=bytearray(old[:jo]);table=bytearray(old[jo:lo])
    lookup=[old[i:i+8] for i in range(lo,io,8)]
    tail0=io+oldni*2;tail=bytearray(old[tail0:])
    names_added=names[n:]
    newlo=jo+len(names)*100;newio=newlo+len(names)*8;nt=newio+2*len(inf)
    for j in range(n):
        o=j*100+96;struct.pack_into('<i',table,o,struct.unpack_from('<i',table,o)[0]+nt-tail0)
    for j,name in enumerate(names_added,n):
        rec=bytearray(100);h=hash_joint(name)
        struct.pack_into('<Hh',rec,2,j,-1);struct.pack_into('<I',rec,8,h);struct.pack_into('<f',rec,12,2.1)
        for o in (16,56):struct.pack_into('<3f3f4f',rec,o,0,0,0,1,1,1,0,0,0,1)
        struct.pack_into('<i',rec,96,nt+len(tail)-(jo+len(table)+96));table.extend(rec)
        tail.extend(name.encode()+b'\0');tail.extend(bytes(-len(tail)%4));lookup.append(struct.pack('<HHI',j,0,h))
    struct.pack_into('<HI',head,14,len(names),len(inf));struct.pack_into('<II',head,24,newlo,newio)
    for off in (32,36,40):
        val=struct.unpack_from('<I',head,off)[0]
        if val not in (0,0xffffffff):struct.pack_into('<I',head,off,val+nt-tail0)
    result=head+table+b''.join(sorted(lookup,key=lambda r:struct.unpack_from('<I',r,4)[0]))+inf.astype('<u2').tobytes()+tail
    struct.pack_into('<I',result,0,len(result))
    return bytes(result)

def anm(D):
    names=D['names'].tolist();L=D['local'];p,s,q=decompose(L.astype(float));n=len(names);f=len(L)
    # v5 dictionaries share one vector pool for translation and scale.
    v,idx=np.unique(np.round(np.stack((p,s),axis=-2).reshape(-1,3),5).astype('<f4'),axis=0,return_inverse=True)
    idx=idx.reshape(f,n,2)
    omit=np.argmax(abs(q),axis=-1);sgn=np.take_along_axis(q,omit[...,None],axis=-1)[...,0]
    qq=q*np.where(sgn<0,-1,1)[...,None];three=qq[np.arange(4)!=omit[...,None]].reshape(f,n,3)
    enc=np.rint((three+1/np.sqrt(2))*32767/np.sqrt(2)).clip(0,32767).astype('u8')
    bits=(omit.astype('u8')<<45)|(enc[...,0]<<30)|(enc[...,1]<<15)|enc[...,2]
    uq,ids=np.unique(bits,return_inverse=True);assert len(uq)<65536 and len(v)<65536
    qbytes=np.stack([(uq>>(16*i))&65535 for i in range(3)],axis=-1).astype('<u2').tobytes()
    # Raw v5 stores contiguous tables with relative offsets from byte 12.
    h=bytearray((BASE/'attack1.anm').read_bytes()[:76]);vo=len(h);qo=vo+v.nbytes;ho=qo+len(qbytes);fo=ho+4*n
    body=v.tobytes()+qbytes+np.array([hash_joint(x) for x in names],'<u4').tobytes()+np.concatenate((idx,ids.reshape(f,n,1)),axis=-1).astype('<u2').tobytes()
    struct.pack_into('<I',h,12,len(h)+len(body)-12);struct.pack_into('<IIfI',h,28,n,f,1/30,ho-12);struct.pack_into('<III',h,52,vo-12,qo-12,fo-12)
    return bytes(h)+body

def billboard(team,i):
    name='BLG_Recall_Badge_'+team;path='Characters/Gwen/Skins/Skin0/Particles/'+name;k=fmt_key(path)
    # Explicit camera-facing quads; tiny linger window permits immediate cancellation.
    block=f'''    {k} = VfxSystemDefinitionData {{
        complexEmitterDefinitionData: list[pointer] = {{
            VfxEmitterDefinitionData {{
                emitterName: string = "{name}"
                isSingleParticle: flag = true
                particleLinger: option[f32] = {{ 0 }}
                emitterLinger: option[f32] = {{ 0 }}
                bindWeight: embed = ValueFloat {{ constantValue: f32 = 1 }}
                rate: embed = ValueFloat {{ constantValue: f32 = 1 }}
                lifetime: option[f32] = {{ 8 }}
                particleLifetime: embed = ValueFloat {{ constantValue: f32 = 8 }}
                birthScale0: embed = ValueVector3 {{ constantValue: vec3 = {{ {WIDTH:g}, {WIDTH:g}, 1 }} }}
                isLocalOrientation: flag = false
                depthBiasFactors: vec2 = {{ -1, -110 }}
                blendMode: u8 = 1
                pass: i16 = 72
                texture: string = "{ROOT}particles/blg_recall/{team.lower()}.tex"
            }}
        }}
        visibilityRadius: f32 = 540
        particleName: string = "{name}"
        particlePath: string = "{path}"
        objectPath: hash = {k}
    }}'''
    event=f'''{fmt_key(name+'_event')} = ParticleEventData {{
                        mEffectKey: hash = {fmt_key(name)}
                        mParticleEventDataPairList: list[embed] = {{
                            ParticleEventDataPair {{ mBoneName: hash = {fmt_key('RC_Badge'+str(i))} }}
                        }}
                    }}'''
    return block,fmt_key(name)+' = '+k,event

if __name__=='__main__':
    from source_package import pack
    pack()
