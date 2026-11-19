"""Read the specific SKL0 and ANM4 layouts used by the installed base Ziggs."""
from pathlib import Path
import struct

import numpy as np


BASE = Path(__file__).resolve().parent / "base"


def unpack(data, offset, fmt):
    return struct.unpack_from("<" + fmt, data, offset)


def transform(position, scale, rotation):
    x, y, z, w = rotation
    a = np.eye(4)
    a[:3, :3] = np.array([
        [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
        [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)],
    ]) @ np.diag(scale)
    a[:3, 3] = position
    return a


class Rig:
    def __init__(self):
        d = (BASE/"ziggs.skl").read_bytes()
        assert unpack(d, 4, "II") == (0x22FD4FC3, 0)
        self.names, self.parents, self.hashes = [], [], []
        self.local, self.bind = [], []
        count, ni, jo, _, io = unpack(d, 14, "HIIII")
        self.influences = unpack(d, io, str(ni)+"H")
        for j in range(count):
            k = jo+100*j
            index, parent = unpack(d,k+2,"Hh")
            assert index == j
            name = k+96+unpack(d,k+96,"i")[0]
            self.names.append(d[name:d.index(b"\0",name)].decode())
            self.parents.append(parent)
            self.hashes.append(unpack(d,k+8,"I")[0])
            local = transform(unpack(d,k+16,"3f"),unpack(d,k+28,"3f"),unpack(d,k+40,"4f"))
            inv = transform(unpack(d,k+56,"3f"),unpack(d,k+68,"3f"),unpack(d,k+80,"4f"))
            self.local.append(local)
            self.bind.append(np.linalg.inv(inv))
        self.bind=np.array(self.bind)
        self.index={n:i for i,n in enumerate(self.names)}
        # The asset stores independently rounded rest transforms and inverse
        # binds. The maximum positional difference in this SKL is 0.25 units.
        local_world=self.world(self.local)
        assert np.max(abs(local_world[:,:3,3]-self.bind[:,:3,3])) < .30
        assert np.max(abs(local_world[:,:3,:3]-self.bind[:,:3,:3])) < .012

    def world(self, local):
        out=[]
        for i,p in enumerate(self.parents):
            out.append(local[i] if p<0 else out[p] @ local[i])
        return np.array(out)

    def animation(self, name):
        d=(BASE/(name+".anm")).read_bytes()
        assert d[:8]==b"r3d2anmd" and unpack(d,8,"I")== (4,)
        joint_count,frame_count,dt=unpack(d,28,"IIf")
        vo,qo,fo=[12+o for o in unpack(d,52,"III")]
        assert fo+frame_count*joint_count*12==len(d)
        ids={h:i for i,h in enumerate(self.hashes)}
        frames=[]
        for f in range(frame_count):
            locals_=self.local.copy()
            seen=set()
            for j in range(joint_count):
                h,t,s,r=unpack(d,fo+12*(f*joint_count+j),"IHHH")
                k=ids[h]
                assert k not in seen
                seen.add(k)
                locals_[k]=transform(unpack(d,vo+12*t,"3f"),unpack(d,vo+12*s,"3f"),
                                     unpack(d,qo+16*r,"4f"))
            frames.append(self.world(locals_))
        return np.array(frames),dt


if __name__=="__main__":
    rig=Rig()
    for name in ("idle1","run","spell1","attack1"):
        f,dt=rig.animation(name)
        print(name,len(f),dt)
        for frame in [0,len(f)//4,len(f)//2]:
            print(frame, {n:f[frame,rig.index[n],:3,3].round().astype(int).tolist()
                          for n in ("head","Hip","L_hand","R_hand","Bomb","Bomb_b","Bomb_c",
                                    "L_foot","R_foot")})
