"""Bake the classic Worlds cup prop in the installed EDG Aphelios skin to a W decal."""
from pathlib import Path
import math
import struct

import numpy as np
from PIL import Image, ImageChops, ImageFilter
from w_art import game_texture

HERE = Path(__file__).resolve().parent
STOCK = HERE / 'stock'


def trophy_mesh():
    data = (STOCK/'aphelios_skin18.skn').read_bytes()
    magic, major, minor, count = struct.unpack_from('<IHHI',data)
    assert (magic,major,minor)==(0x112233,4,1)
    parts = [struct.unpack_from('<64s4I',data,12+80*i) for i in range(count)]
    [(name, first, nverts, start, nindices)] = [p for p in parts if p[0].rstrip(b'\0')==b'SummonersCup']
    offset = 12+80*count
    _,ni,nv,stride,layout = struct.unpack_from('<5I',data,offset)
    assert (stride,layout)==(52,0)
    indices = np.frombuffer(data,'<u2',ni,offset+60)[start:start+nindices].astype(int)-first
    assert indices.min()>=0 and indices.max()<nverts
    fmt = np.dtype(dict(names=['p','n','uv'], formats=[('<f4',3),('<f4',3),('<f4',2)],
                        offsets=[0,32,44],itemsize=stride))
    return np.frombuffer(data,fmt,nv,offset+60+ni*2)[first:first+nverts],indices.reshape(-1,3)


def bake(yaw=45.):
    verts,faces = trophy_mesh()
    tex = np.asarray(game_texture(STOCK/'aphelios_skin18_summonerscup_tx_cm.tex').convert('RGB'),dtype=float)/255
    az,el = math.radians(yaw), math.radians(6)
    right=np.array([math.cos(az),0,-math.sin(az)])
    front=np.array([math.sin(az)*math.cos(el),math.sin(el),math.cos(az)*math.cos(el)])
    up=np.cross(front,right)
    pos=np.column_stack((verts['p']@right,-verts['p']@up,verts['p']@front))
    extent=np.ptp(pos[:,:2],axis=0)
    xy=(pos[:,:2]-(pos[:,:2].min(0)+extent*.5))*468/extent.max()+256
    normal=np.column_stack((verts['n']@right,verts['n']@up,verts['n']@front))
    out=np.zeros((512,512,4),dtype=np.uint8)
    depth=np.full((512,512),-np.inf)
    for ids in faces:
        a,b,c=xy[ids]
        xmin,ymin=np.maximum(0,np.floor(xy[ids].min(0))).astype(int)
        xmax,ymax=np.minimum(512,np.ceil(xy[ids].max(0))+1).astype(int)
        y,x=np.mgrid[ymin:ymax,xmin:xmax]
        v,w=b-a,c-a
        det=v[0]*w[1]-v[1]*w[0]
        if abs(det)<1.e-6:
            continue
        dx,dy=x+.5-a[0],y+.5-a[1]
        j=(dx*w[1]-dy*w[0])/det
        k=(dy*v[0]-dx*v[1])/det
        bary=np.stack((1-j-k,j,k),axis=-1)
        z=bary@pos[ids,2]
        zbuf=depth[ymin:ymax,xmin:xmax]
        visible=(bary.min(-1)>=0)&(z>zbuf)
        if not visible.any():
            continue
        weights=bary[visible]
        uv=weights@verts['uv'][ids]
        tx=(uv[:,0]*(tex.shape[1]-1)).round().astype(int).clip(0,tex.shape[1]-1)
        ty=(uv[:,1]*(tex.shape[0]-1)).round().astype(int).clip(0,tex.shape[0]-1)
        color=tex[ty,tx]
        n=weights@normal[ids]
        n/=np.maximum(.0001,np.linalg.norm(n,axis=1,keepdims=True))
        lit=np.clip(n@np.array([-.43,.64,.63]),0,1)
        glint=np.clip(n@np.array([-.28,.45,.85]),0,1)**18
        rim=(1-np.abs(n[:,2]).clip(0,1))**2
        steel=color*(.73+.31*lit[:,None])+.19+.20*glint[:,None]
        steel+=rim[:,None]*np.array([.13,.11,.08])
        pixels=out[ymin:ymax,xmin:xmax]
        pixels[visible,:3]=np.uint8(np.clip(steel,0,1)*255)
        # The lower silver plinth is a fainter inlay under the champion.
        # Keep the raised rim and the sapphire bowl most legible at game scale.
        lower=np.clip((y[visible]-304)/155,0,1)
        pixels[visible,3]=np.uint8(255*(1-.24*lower))
        zbuf[visible]=z[visible]
    image=Image.fromarray(out)
    alpha=image.getchannel('A')
    halo=Image.new('RGBA',image.size,(147,224,255,0))
    halo.putalpha(alpha.filter(ImageFilter.GaussianBlur(8)).point(lambda a: round(a*.34)))
    stroke=Image.new('RGBA',image.size,(255,225,173,0))
    stroke.putalpha(ImageChops.subtract(alpha.filter(ImageFilter.MaxFilter(5)),alpha).point(lambda a:round(a*.87)))
    return Image.alpha_composite(Image.alpha_composite(halo,stroke),image)


if __name__=='__main__':
    bake().save(HERE/'art'/'w_worlds_cup.png')
