"""Lossless native RGBA8 with alpha-weighted, linear-light diffuse mipmaps."""
import struct
import numpy as np
SRGB=np.arange(256,dtype='f')/255
LINEAR=np.where(SRGB<=.04045,SRGB/12.92,((SRGB+.055)/1.055)**2.4)
def downsample(src):
    h,w=src.shape[:2];dx=2 if w>1 else 1;dy=2 if h>1 else 1
    dst=np.empty((max(1,h//2),max(1,w//2),4),'u1')
    for y0 in range(0,len(dst),96):
        rows=min(96,len(dst)-y0);size=(rows,dst.shape[1])
        rgb=np.zeros((*size,3),'f');alpha=np.zeros(size,'f')
        for iy in range(dy):
            for ix in range(dx):
                v=src[y0*dy+iy:(y0+rows)*dy:dy,ix::dx]
                a=v[:,:,3].astype('f');alpha+=a
                rgb+=LINEAR[v[:,:,:3]]*a[:,:,None]
        rgb/=np.maximum(1,alpha[:,:,None])
        srgb=np.where(rgb<=.0031308,12.92*rgb,1.055*np.power(rgb,1/2.4)-.055)
        target=dst[y0:y0+rows];target[:,:,:3]=np.rint(255*np.clip(srgb,0,1)).astype('u1')
        target[:,:,3]=np.rint(alpha/(dx*dy)).astype('u1')
        target[target[:,:,3]==0,:3]=0
    return dst
def encode(im):
    src=np.asarray(im.convert('RGBA'));w,h=im.size
    assert (w&(w-1))==0 and (h&(h-1))==0
    levels=[]
    while True:
        levels.append(src[:,:,[2,1,0,3]].tobytes())
        if src.shape[:2]==(1,1):break
        src=downsample(src)
    return struct.pack('<4sHH4B',b'TEX\0',w,h,1,20,0,1)+b''.join(reversed(levels))

