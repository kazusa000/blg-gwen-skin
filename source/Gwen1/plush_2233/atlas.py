"""Fabric, embroidery and face UVs for the two Gwen marionettes."""
from pathlib import Path
import math
import numpy as np
from PIL import Image, ImageDraw
from collections import deque

HERE=Path(__file__).resolve().parent
SKIN=HERE.parents[2]/'skin'/'Gwen1'
WORK=HERE/'build'
SIZE=4096
CELL=384
COLORS={
 'navy':(43,58,91),'blue':(43,66,128),'blue_mid':(59,89,155),'blue_lit':(85,114,172),
 'ice':(178,196,215),'ice_lit':(207,218,231),'ice_shadow':(144,164,191),
 'ivory':(239,226,210),'cream':(255,239,218),'skin':(248,215,188),'gold':(218,179,128),
 'rose':(220,128,161),'rose_lit':(242,174,191),'ink':(57,46,61),'pink_gem':(228,132,166),
 'azure':(106,178,224),'sole':(55,64,93),'white':(251,242,225),'blush':(224,157,147),
 'pin_blue':(53,119,204),'pin_rose':(211,76,143),'champagne':(219,177,112)}
RECT={name:((i%8)*CELL,(i//8)*CELL,CELL,CELL) for i,name in enumerate(COLORS)}
RECT.update(face22=(0,1280,2048,1020),face33=(0,2304,2048,1020),badge=(2304,1320,768,368))
ATLAS=SKIN/'textures'/'gwen-2233-plush.png'

def cloth(w,h,base,seed):
    rng=np.random.default_rng(seed)
    x,y=np.meshgrid(np.arange(w),np.arange(h))
    low=np.array(Image.fromarray(rng.integers(0,255,(max(3,h//17),max(3,w//17)),dtype='uint8')).resize((w,h),Image.Resampling.BICUBIC))/255-.5
    # Fine warp and weft survive the game's mip filtering as a soft textile response.
    warp=1.05*np.sin(x*.53+.09*np.sin(y*.035))
    weft=.90*np.sin(y*.57+.08*np.sin(x*.041))
    f=rng.normal(0,1.8,(h,w))+low*6+warp+weft+1.1*np.sin(x*1.52+.32*y)+1.2*np.cos(y*1.35-.13*x)
    return Image.fromarray(np.uint8(np.clip(np.array(base)+f[:,:,None],0,255)),'RGB')

def stitch_face(source,num,canvas):
    # Source is the approved embroidery. Isolate its thread from the skin/hair,
    # then place it on the curved head UV; the sides and back have real fabric.
    crops=([(268,300,367,394),(442,282,531,378),(382,369,448,424)] if num==22 else
           [(687,321,784,398),(859,305,952,392),(785,405,836,429)])
    boxes=[(.414,.510,.085,.192),(.586,.510,.085,.192),(.50,.624,.053,.090 if num==22 else .034)]
    for index,(crop,(u,v,uw,vh)) in enumerate(zip(crops,boxes)):
        raw=source.crop(crop).convert('RGB'); a=np.asarray(raw).astype(float);r,g,b=a.transpose(2,0,1)
        # Isolate the continuous thread shape; exclude loose cheek marks, bangs
        # and skin highlights that happen to fall inside the rectangular crop.
        thread=(r-g>24)&(r-b>13)&(g<143)
        seen=set();largest=[]
        for y,x in zip(*np.nonzero(thread)):
            if (y,x) in seen:continue
            run=[(y,x)];seen.add((y,x));queue=deque(run)
            while queue:
                yy,xx=queue.popleft()
                for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)):
                    ny,nx=yy+dy,xx+dx
                    if 0<=ny<thread.shape[0] and 0<=nx<thread.shape[1] and thread[ny,nx] and (ny,nx) not in seen:
                        queue.append((ny,nx));run.append((ny,nx));seen.add((ny,nx))
            if len(run)>len(largest):largest=run
        mask=np.zeros_like(r)
        ys,xs=np.array(largest).T;mask[ys,xs]=1
        for yy,row in enumerate(mask):
            ids=np.where(row>0)[0]
            if len(ids)>2:mask[yy,ids[0]:ids[-1]+1]=1
        raw.putalpha(Image.fromarray(np.uint8(mask*255)))
        w,h=canvas.size;ew,eh=round(w*uw),round(h*vh)
        assert 0<u<1 and 0<v<1 and mask.sum()>8
        raw=raw.resize((ew,eh),Image.Resampling.LANCZOS)
        canvas.paste(raw,(round(w*u-ew/2),round(h*v-eh/2)),raw)
    draw=ImageDraw.Draw(canvas)
    for u in (.375,.617):
        for i in range(3):
            x=round((u+i*.008)*canvas.width);y=round((.618-i*.005)*canvas.height)
            draw.line((x,y,x+3,y-7),fill=(214,135,134),width=3)

def make_atlas():
    WORK.mkdir(parents=True,exist_ok=True)
    ref=Image.open(SKIN/'reference'/'2233-plush-concept-v1.png').convert('RGB')
    canvas=Image.new('RGB',(SIZE,SIZE),COLORS['ivory'])
    for i,(name,color) in enumerate(COLORS.items()):
        x,y,w,h=RECT[name];canvas.paste(cloth(w,h,color,22+i),(x,y))
    for n in (22,33):
        x,y,w,h=RECT['face'+str(n)]
        face=cloth(w,h,COLORS['skin'],n);stitch_face(ref,n,face);canvas.paste(face,(x,y))
    # Use the actual embroidered BLG wordmark from the approved cape.
    x,y,w,h=RECT['badge'];badge=cloth(w,h,COLORS['ivory'],34)
    raw=ref.crop((236,552,356,609));a=np.asarray(raw).astype(float);r,g,b=a.transpose(2,0,1)
    mask=np.clip(np.maximum((b-r+10)*2.7,(r-g-35)*2.3),0,255)*np.clip((218-g)/45,0,1)
    raw.putalpha(Image.fromarray(np.uint8(mask)))
    raw=raw.resize((w,h),Image.Resampling.LANCZOS);badge.paste(raw,(0,0),raw);canvas.paste(badge,(x,y))
    canvas.save(ATLAS)
    return canvas

def uv(tile,u,v):
    x,y,w,h=RECT[tile]
    return ((x+4+u*(w-8))/SIZE,(y+4+v*(h-8))/SIZE)

