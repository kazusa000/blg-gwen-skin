from pathlib import Path
import json
import struct
from functools import cached_property
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
BASE=HERE/'rig-study'
SKIN=HERE.parents[1]/'skin'/'Gwen1'

from game_formats import transform, unpack


def decode_quat(v):
    """Decode League's 48-bit smallest-three quaternion, in x/y/z/w order."""
    v=np.asarray(v,dtype=np.uint64)
    bits=v[...,0]|(v[...,1]<<16)|(v[...,2]<<32)
    omit=((bits>>45)&3).astype(np.intp)
    three=np.stack([((bits>>n)&32767).astype(np.float32)*
                    (np.sqrt(np.float32(2))/np.float32(32767))-
                    np.float32(1/np.sqrt(2)) for n in (30,15,0)],axis=-1)
    q=np.empty(bits.shape+(4,),dtype=np.float32)
    for omitted in range(4):
        mask=omit==omitted
        if not np.any(mask):
            continue
        q[mask,:omitted]=three[mask,:omitted]
        q[mask,omitted]=np.sqrt(np.maximum(
            np.float32(0),np.float32(1)-np.sum(three[mask]*three[mask],axis=-1)))
        q[mask,omitted+1:]=three[mask,omitted:]
    return q


def _catmull_weights(amount, ease_in, ease_out):
    """LeagueToolkit's component-wise Catmull-Rom weights (f32 inputs)."""
    t=np.float32(amount); a=np.float32(ease_in); b=np.float32(ease_out)
    m0=((np.float32(2)-t)*t-np.float32(1))*(t*a)
    m1=(((np.float32(2)-b)*t+(b-np.float32(3)))*(t*t))+np.float32(1)
    m2=(((np.float32(3)-a*np.float32(2)+(a-np.float32(2))*t)*t)+a)*t
    m3=((t-np.float32(1))*t)*(t*b)
    return np.stack((m0,m1,m2,m3),axis=-1).astype(np.float32,copy=False)


def _catmull_sample(times, values, when, parametrized, quaternion=False):
    """Sample four League hot-frame controls, preserving the game's f32 math."""
    t1=times[:,1].astype(np.int32)
    t2=times[:,2].astype(np.int32)
    span=np.maximum(t2-t1,0).astype(np.float32)
    nonzero=span>0
    safe_span=np.where(nonzero,span,np.float32(1))
    if parametrized:
        eps=np.float32(1.e-6)
        amount=np.maximum(np.float32(when)-t1,0)/(safe_span+eps)
        ease_in=safe_span/(np.maximum(t2-times[:,0].astype(np.int32),0)+eps)
        ease_out=safe_span/(np.maximum(times[:,3].astype(np.int32)-t1,0)+eps)
    else:
        amount=np.maximum(np.float32(when)-t1,0)/safe_span
        ease_in=ease_out=np.float32(.5)
    weights=_catmull_weights(amount,ease_in,ease_out)
    result=(weights[:,1,None]*values[:,1] + weights[:,0,None]*values[:,0] +
            weights[:,3,None]*values[:,3] + weights[:,2,None]*values[:,2])
    result=np.where(nonzero[:,None],result,values[:,1])
    if quaternion:
        length=np.sqrt(np.sum(result*result,axis=-1,keepdims=True,dtype=np.float32))
        result=np.divide(result,length,out=result,where=length>np.float32(1.e-12))
    return result


class _CompressedEvaluator:
    """Sequential r3d2canm evaluator, ported from LeagueToolkit's hot frames.

    The 128-byte header's offsets are based at byte 12. Key records are 10 bytes;
    each jump-cache entry has 12 key indices per joint. See LeagueToolkit's
    ``ltk_anim`` compressed ``read.rs``, ``frame.rs``, and ``evaluator.rs``.
    """
    _IDENTITY=np.array([0,0,0,1],dtype=np.float32)

    def __init__(self, data, joint_count):
        self.data=data
        self.joint_count=joint_count
        self.last_time=-1.
        self.cursor=0
        self.frame_count=unpack(data,28,'I')[0]
        self.cache_count=unpack(data,32,'i')[0]
        self.duration=unpack(data,36,'f')[0]
        self.flags=unpack(data,20,'I')[0]
        self.frame_off=12+unpack(data,116,'I')[0]
        self.frames=np.frombuffer(data,'<u2',self.frame_count*5,self.frame_off).reshape(-1,5)
        self.bounds=np.frombuffer(data,'<f4',12,68).reshape(4,3)
        if self.cache_count:
            cache_off=12+unpack(data,120,'I')[0]
            width=2 if self.frame_count<0x10001 else 4
            dtype='<u2' if width==2 else '<u4'
            self.cache_sentinel=0xffff if width==2 else 0xffffffff
            self.caches=np.frombuffer(data,dtype,
                self.cache_count*joint_count*12,cache_off).reshape(self.cache_count,joint_count,12)
        else:
            self.cache_sentinel=0xffff
            self.caches=None

    def _initialize(self,time):
        # Jump-cache records contain 4 key indices for rotation, translation,
        # and scale for each joint. The all-ones index marks an absent channel.
        joint_count=self.joint_count
        cache_count=self.cache_count
        duration=self.duration
        if cache_count<=0 or duration<=0:
            self.cursor=0
            self.times=np.zeros((joint_count,3,4),dtype=np.uint16)
            self.values=np.zeros((joint_count,3,4,4),dtype=np.float32)
            self.values[:,0]=self._IDENTITY
            self.values[:,2]=np.array([1,1,1,0],dtype=np.float32)
            return
        cache_id=min(int(np.float32(cache_count)*(
            np.float32(time)/np.float32(duration))),cache_count-1)
        cache=self.caches[cache_id]
        # Layout per joint: rotation[4], translation[4], scale[4].
        values=np.zeros((joint_count,3,4,4),dtype=np.float32)
        values[:,0]=self._IDENTITY
        values[:,2]=np.array([1,1,1,0],dtype=np.float32)
        times=np.zeros((joint_count,3,4),dtype=np.uint16)
        indices=cache.reshape(joint_count,3,4)
        valid=indices!=self.cache_sentinel
        self.cursor=0
        # The runtime uses the maximum cache index then starts at the next key.
        if np.any(valid):
            self.cursor=int(indices[valid].max())
        self.cursor+=1
        for joint,channel,keyslot in zip(*np.nonzero(valid)):
            idx=int(indices[joint,channel,keyslot])
            row=self.frames[idx]
            times[joint,channel,keyslot]=row[0]
            packed=row[2:5]
            if channel==0:
                values[joint,channel,keyslot]=decode_quat(packed[None,:])[0]
            else:
                bounds_i=0 if channel==1 else 2
                lo,hi=self.bounds[bounds_i:bounds_i+2]
                values[joint,channel,keyslot,:3]=lo+(hi-lo)*(
                    packed.astype(np.float32)/np.float32(65535))
        # Keep rotation controls in a continuous hemisphere exactly as runtime.
        for joint in range(joint_count):
            for i in range(1,4):
                if np.dot(values[joint,0,i],values[joint,0,0])<0:
                    values[joint,0,i]*=-1
        self.times,self.values=times,values

    def _fetch(self, joint, channel, time, packed):
        vals=self.values[joint,channel]
        tms=self.times[joint,channel]
        vals[:-1]=vals[1:]
        tms[:-1]=tms[1:]
        tms[3]=time
        if channel==0:
            vals[3]=decode_quat(packed[None,:])[0]
            for i in range(1,4):
                if np.dot(vals[i],vals[0])<0:
                    vals[i]*=-1
        else:
            bounds_i=0 if channel==1 else 2
            lo,hi=self.bounds[bounds_i:bounds_i+2]
            vals[3,:3]=lo+(hi-lo)*(packed.astype(np.float32)/np.float32(65535))

    def evaluate(self,time):
        if (self.last_time<0 or self.last_time>time or
            (self.cache_count>0 and time-self.last_time>self.duration/self.cache_count)):
            self._initialize(time)
        if self.duration<=0:
            compressed_time=0
        else:
            compressed_time=int(np.float32(np.float32(time)/np.float32(self.duration)*
                                           np.float32(65535)))
            compressed_time=min(max(compressed_time,0),65535)
        while self.cursor<self.frame_count:
            row=self.frames[self.cursor]
            tag=int(row[1]); joint=tag&0x3fff; channel=tag>>14
            if compressed_time<int(self.times[joint,channel,2]):
                break
            self._fetch(joint,channel,int(row[0]),row[2:5])
            self.cursor+=1
        self.last_time=time
        parametrized=bool(self.flags&(1<<2))
        rotations=_catmull_sample(self.times[:,0,:],self.values[:,0,:,:],
                                  compressed_time,parametrized,True)
        translations=_catmull_sample(self.times[:,1,:],self.values[:,1,:,:3],
                                     compressed_time,parametrized)
        scales=_catmull_sample(self.times[:,2,:],self.values[:,2,:,:3],
                               compressed_time,parametrized)
        return translations,scales,rotations


class Gwen:
    def __init__(self):
        d=(BASE/'gwen_base.skl').read_bytes()
        assert unpack(d,4,'II')==(0x22FD4FC3,0)
        n,ni,off,_,io=unpack(d,14,'HIIII')
        self.influences=np.array(unpack(d,io,f'{ni}H'))
        self.names=[];self.parents=[];self.hashes=[];self.local=[];self.bind=[]
        for i in range(n):
            k=off+i*100
            idx,parent,h=unpack(d,k+2,'Hh2xI')
            assert idx==i
            s=k+96+unpack(d,k+96,'i')[0]
            self.names.append(d[s:d.index(0,s)].decode())
            self.parents.append(parent);self.hashes.append(h)
            def matrix(o):
                return transform(unpack(d,o,'3f'),unpack(d,o+12,'3f'),unpack(d,o+24,'4f'))
            self.local.append(matrix(k+16));self.bind.append(np.linalg.inv(matrix(k+56)))
        self.parents=np.array(self.parents);self.local=np.array(self.local);self.bind=np.array(self.bind)
        self.byhash={h:j for j,h in enumerate(self.hashes)}
        assert len(self.byhash)==n
        d=(BASE/'gwen_base.skn').read_bytes()
        magic,major,minor,parts=unpack(d,0,'IHHI');assert (magic,major,minor)==(0x112233,4,1)
        self.sections={}
        for i in range(parts):
            k=12+i*80
            self.sections[d[k:k+64].split(b'\0')[0].decode()]=unpack(d,k+64,'4I')
        off=12+80*parts
        flags,ni,nv,stride,layout=unpack(d,off,'5I');assert (stride,layout)==(52,0) and flags in (0,2)
        off+=60
        self.tri=np.frombuffer(d,'<u2',ni,off).reshape(-1,3)
        if flags & 2:
            self.tri=self.tri.astype(np.uint32)
            for base,count,first,length in self.sections.values():
                part=self.tri.ravel()[first:first+length]
                assert count<=65536 and int(part.max())<count
                part+=base
        dt=np.dtype([('p','<f4',3),('i','u1',4),('w','<f4',4),('n','<f4',3),('uv','<f4',2)])
        self.verts=np.frombuffer(d,dt,nv,off+ni*2)
        assert self.tri.max()<nv and np.allclose(self.verts['w'].sum(1),1)
        self.joints=self.influences[self.verts['i']]
    @cached_property
    def weights(self):
        weights=np.zeros((len(self.verts),len(self.names)))
        np.add.at(weights,(np.arange(len(self.verts))[:,None],self.joints),self.verts['w'])
        return weights

    def sample(self,name):
        """Return (joint_ids, local positions, scales, xyzw rotations, dt).

        Raw and compressed formats share this contract. Values stay in League's
        local rig axes here; the existing Blender bind path performs its usual
        axis conversion after sampling.
        """
        d=(BASE/(name+'.anm')).read_bytes()
        if d[:8]==b'r3d2canm':
            version=unpack(d,8,'I')[0]
            if version not in (1,2,3):
                raise ValueError(f'unsupported compressed ANM version {version}: {name}')
            joint_count,key_count=unpack(d,24,'II')
            cache_count=unpack(d,32,'i')[0]
            duration,fps=unpack(d,36,'ff')
            if (not np.isfinite(duration) or duration<0 or
                not np.isfinite(fps) or fps<=0 or cache_count<0):
                raise ValueError(f'invalid compressed ANM timing/header: {name}')
            frame_off,jump_off,hash_off=[12+o for o in unpack(d,116,'III')]
            jump_width=2 if key_count<0x10001 else 4
            jump_size=cache_count*joint_count*12*jump_width
            if (len(d)<128 or frame_off<128 or jump_off<frame_off+10*key_count or
                hash_off<jump_off+jump_size or hash_off+4*joint_count>len(d)):
                raise ValueError(f'invalid compressed ANM offsets/counts: {name}')
            hashes=np.frombuffer(d,'<u4',joint_count,hash_off)
            try:
                ids=[self.byhash[int(h)] for h in hashes]
            except KeyError as e:
                raise ValueError(f'compressed ANM refers to unknown rig joint hash {e.args[0]:08x}: {name}') from e
            keys=np.frombuffer(d,'<u2',key_count*5,frame_off).reshape(-1,5)
            tags=keys[:,1]
            joint_ids=tags&0x3fff
            kinds=tags>>14
            if key_count and (joint_ids.max()>=joint_count or kinds.max()>2):
                raise ValueError(f'invalid compressed ANM transform tag: {name}')
            # The compressed frame table starts with per-track hot-frame seeds,
            # followed by a runtime cursor stream, so it is not globally sorted.
            # Time order is guaranteed within each joint/transform track.
            for tag in np.unique(tags):
                track_times=keys[tags==tag,0]
                if np.any(track_times[1:]<track_times[:-1]):
                    raise ValueError(f'compressed ANM track keys are not time sorted: {name}')
            # Dense samples at the source animation's native frame cadence.
            # League's duration is stored as an integer number of frame steps.
            sample_count=int(round(duration*fps))+1
            evaluator=_CompressedEvaluator(d,joint_count)
            positions=np.empty((sample_count,joint_count,3),dtype=np.float32)
            scales=np.empty_like(positions)
            rotations=np.empty((sample_count,joint_count,4),dtype=np.float32)
            dt=1./fps
            for frame in range(sample_count):
                time=np.float32(min(frame*dt,duration))
                positions[frame],scales[frame],rotations[frame]=evaluator.evaluate(time)
            return ids,positions,scales,rotations,dt
        if d[:8]!=b'r3d2anmd' or unpack(d,8,'I')!=(5,):
            raise ValueError(f'unsupported ANM magic/version: {name}')
        n,f,dt,h=unpack(d,28,'IIfI')
        vo,qo,fo=[12+o for o in unpack(d,52,'III')];ho=12+h
        assert (qo-vo)%12==0 and (ho-qo)%6==0 and ho+4*n==fo and fo+f*n*6==len(d)
        vec=np.frombuffer(d,'<f4',(qo-vo)//4,vo).reshape(-1,3)
        quat=decode_quat(np.frombuffer(d,'<u2',(ho-qo)//2,qo).reshape(-1,3))
        ids=[self.byhash[int(h)] for h in np.frombuffer(d,'<u4',n,ho)]
        indices=np.frombuffer(d,'<u2',f*n*3,fo).reshape(f,n,3)
        return ids,vec[indices[:,:,0]],vec[indices[:,:,1]],quat[indices[:,:,2]],dt

    def track_ranges(self,name):
        ids,pos,scale,quat,_=self.sample(name)
        channels=[(j,pos[:,k],scale[:,k],quat[:,k]) for k,j in enumerate(ids)]
        result={}
        for j,pos,scale,quat in channels:
            dist=lambda v: float(np.linalg.norm(v-v[:1],axis=1).max()) if len(v) else 0
            angles=np.degrees(2*np.arccos(np.clip(np.abs(quat@quat[0]),0,1))) if len(quat) else [0]
            result[self.names[j]]=(round(dist(pos),3),round(float(max(angles)),3),round(dist(scale),4))
        return result


if __name__=='__main__':
    r=Gwen()
    clips={f.stem:r.track_ranges(f.stem) for f in sorted(BASE.glob('*.anm'))}
    groups={'ponytails':[n for n in r.names if n.startswith(('L_Hair','R_Hair')) and n[-1].isdigit()],
            'fringe':['Bangs1','Bangs2'],'skirt':[n for n in r.names if '_Skirt_' in n],
            'eyes':['L_Eye','R_Eye'],'lids':[n for n in r.names if n.endswith(('UpLid','LoLid'))],
            'jaw':['Jaw'],'corners':['L_MouthCrnr','R_MouthCrnr'],'shears':['Scissors_A','Scissors_B']}
    def active(value):
        return value[0]>.10 or value[1]>1 or value[2]>.013
    record={'joints':len(r.names),'influence_slots':len(r.influences),'groups':groups,'clips':clips,
            'weights':{name:int((r.weights[:,j]>1.e-5).sum()) for j,name in enumerate(r.names)}}
    (BASE/'audit.json').write_text(json.dumps(record,indent=1),encoding='utf-8')
    print('in use',int((r.weights.max(0)>1.e-5).sum()))
    for group,names in groups.items():
        print(group,{n:record['weights'][n] for n in names},[c for c,tracks in clips.items() if any(active(tracks.get(n,(0,0,0))) for n in names)])
    print('typical',[(n,r.bind[r.names.index(n),:3,3].round(1).tolist()) for n in ['Head','Jaw','L_Eye','R_Eye','L_UpLid','L_Hair1','L_Hair3','C_Skirt_Front1','C_Skirt_Back1','L_Foot','Scissors_A']])
