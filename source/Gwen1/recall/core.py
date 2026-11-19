"""Shared game-space transforms and working paths for the eight-second recall."""
from pathlib import Path
import sys
import numpy as np
HERE=Path(__file__).resolve().parent
GW=HERE.parent
WORK=HERE/'build'
SKIN=GW.parents[1]/'skin'/'Gwen1'
for path in (GW,GW/'vfx',GW/'plush_2233'):sys.path.insert(0,str(path))
from rig_data import Gwen
from game_formats import transform
TEAM=('HLE','DK','T1','GEN')
ANCHORS=np.array([[-226,100,-168],[226,100,-168],[226,98,162],[-226,98,162]],float)
LOGOS=ANCHORS.copy()
LOGOS[:,0]+=np.sign(LOGOS[:,0])*30
LOGOS[:,1]+=16
CUTS=np.array([32,59,86,116],dtype=float)/30
WIDTH=78.
LENGTH=132.5
CUP_H=125.
SIT=np.array([-12.,CUP_H+3,36.])
BLINKS=(20,46,74,104)
SEAT_BLINK=142
ALL_BLINKS=(*BLINKS,SEAT_BLINK)
SWAP=194
SEAT_PREVIEW=range(SEAT_BLINK-5,SWAP+13)
def joke_frame(tick):
    # Re-time the authored seat exchange. The turnaround holds in the source start after frame 29.
    phase=2*np.pi*(tick-SEAT_BLINK)/34+.82
    return 24.4-4.8*np.cos(phase)
# Widths are in game units. Timing keys are offsets from maximum light at the exchange.
FLASH_CUES=[('Departure','Dash'+str(i),t,108,(-5,0,7)) for i,t in enumerate(BLINKS)]
FLASH_CUES.extend([('Departure','Dash3',SEAT_BLINK,108,(-5,0,7)),
                   ('Change','Change',SEAT_BLINK+2,139,(-4,0,4))])
FLASH_CUES.append(('Change','Change',SWAP,139,(-4,0,4)))
def blink_hidden(frame):
    return any(t-1<=frame<=t for t in ALL_BLINKS)
BASE=GW/'rig-study'
C=np.array([[.02,0,0,0],[0,0,-.02,0],[0,.02,0,0],[0,0,0,1]])
def ease(x):
    x=np.clip(x,0,1)
    return x*x*(3-2*x)
def unit(v):
    return np.array(v)/max(1e-12,np.linalg.norm(v))
def trs(p=(0,0,0),r=None,s=1.):
    out=np.eye(4);out[:3,3]=p;out[:3,:3]=(np.eye(3) if r is None else r)*np.broadcast_to(s,3);return out
def rot(axis,angle):
    a=unit(axis);x,y,z=a;c=np.cos(angle);s=np.sin(angle)
    return np.eye(3)*c+(1-c)*np.outer(a,a)+s*np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
def decompose(m):
    p=m[...,:3,3].copy()
    s=np.linalg.norm(m[...,:3,:3],axis=-2)
    s[...,0]*=np.where(np.linalg.det(m[...,:3,:3])<0,-1,1)
    R=m[...,:3,:3]/np.where(abs(s)>1e-9,s,1)[...,None,:]
    a,b,c,d,e,f,h,i,j=np.moveaxis(R.reshape(R.shape[:-2]+(9,)),-1,0)
    terms=np.stack((1+a-e-j,1-a+e-j,1-a-e+j,1+a+e+j),axis=-1)
    rows=np.stack([np.stack(z,-1) for z in ((terms[...,0],b+d,c+h,i-f),(b+d,terms[...,1],f+i,c-h),(c+h,f+i,terms[...,2],d-b),(i-f,c-h,d-b,terms[...,3]))],axis=-2)
    q=np.take_along_axis(rows,np.argmax(terms,axis=-1)[...,None,None],axis=-2)[...,0,:]
    q=q/np.maximum(1.e-12,np.linalg.norm(q,axis=-1)[...,None])
    return p,s,q
def compose(p,s,q):
    x,y,z,w=np.moveaxis(q,-1,0)
    out=np.zeros(p.shape[:-1]+(4,4))
    R=out[...,:3,:3]
    R[...,0,0]=1-2*(y*y+z*z);R[...,0,1]=2*(x*y-w*z);R[...,0,2]=2*(x*z+w*y)
    R[...,1,0]=2*(x*y+w*z);R[...,1,1]=1-2*(x*x+z*z);R[...,1,2]=2*(y*z-w*x)
    R[...,2,0]=2*(x*z-w*y);R[...,2,1]=2*(y*z+w*x);R[...,2,2]=1-2*(x*x+y*y)
    R*=s[...,None,:];out[...,:3,3]=p;out[...,3,3]=1
    return out
def mix(a,b,t):
    if t<=0:return a.copy()
    if t>=1:return b.copy()
    p,s,q=decompose(a);P,S,Q=decompose(b)
    Q=Q*np.where((q*Q).sum(-1,keepdims=True)<0,-1,1)
    u=(1-t)*q+t*Q;u/=np.maximum(np.linalg.norm(u,axis=-1,keepdims=True),1e-10)
    return compose(p*(1-t)+P*t,s*(1-t)+S*t,u)
def world(local,parents):
    w=local.copy()
    for j,p in enumerate(parents):
        if p>=0:w[...,j,:,:]=w[...,p,:,:]@w[...,j,:,:]
    return w
def fmt_key(name):
    h=2166136261
    for c in name.lower().encode():h=((h^c)*16777619)&0xffffffff
    return f'0x{h:08x}'
def clip(g,key):
    ids,p,s,q,dt=g.sample(key)
    a=np.broadcast_to(g.local,(len(p),)+g.local.shape).copy()
    a[:,ids]=compose(p,s,q)
    return a
def sample(frames,f):
    f=np.clip(f,0,len(frames)-1);i=int(f)
    return mix(frames[i],frames[min(len(frames)-1,i+1)],float(f-i))
def inward(anchor):
    return unit([-anchor[0],0,-anchor[2]])

