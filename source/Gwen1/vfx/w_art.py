"""Native-resolution BLG champion W particle textures, laid out from Skin0 UVs."""
from pathlib import Path
from io import BytesIO
import struct
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
STOCK = HERE/'stock'
ART = HERE/'art'
ART.mkdir(exist_ok=True)
BLUE = np.array((52, 174, 235), dtype=np.float32)
PINK = np.array((241, 103, 182), dtype=np.float32)
PALE = np.array((250, 246, 240), dtype=np.float32)
GOLD = np.array((226, 186, 118), dtype=np.float32)


def game_texture(path):
    data=path.read_bytes()
    if data[:4]!=b'TEX\0' or data[9]!=12:
        raise ValueError(f'Expected a BC3 game texture: {path}')
    width,height=struct.unpack_from('<HH',data,4)
    size=16*((width+3)//4)*((height+3)//4)
    buf=BytesIO()
    Image.new('RGBA',(4,4)).save(buf,format='DDS',pixel_format='DXT5')
    header=bytearray(buf.getvalue()[:128])
    struct.pack_into('<III',header,12,height,width,size)
    return Image.open(BytesIO(header+data[-size:])).convert('RGBA')


def uv_strip():
    # The native W wall mesh covers U=0..1 and V=.192..668. Put its stitched
    # band precisely in that UV strip, so it wraps once around the stock mesh.
    size=(1024,256)
    s=2
    im=Image.new('RGBA',(size[0]*s,size[1]*s),(0,0,0,0))
    d=ImageDraw.Draw(im)
    def line(points,fill,width):
        d.line([(round(x*s),round(y*s)) for x,y in points],fill=fill,width=round(width*s),joint='curve')
    # Texture V maps upward, so .192-.668 becomes image y 85..207.
    line([(0,87),(1024,87)],(*tuple(GOLD.astype(int)),170),5)
    line([(0,91),(1024,91)],(*tuple(PALE.astype(int)),225),2)
    line([(0,111),(1024,111)],(*tuple(GOLD.astype(int)),185),2)
    line([(0,180),(1024,180)],(*tuple(GOLD.astype(int)),175),2)
    line([(0,199),(1024,199)],(*tuple(GOLD.astype(int)),205),3)
    line([(0,203),(1024,203)],(*tuple(PALE.astype(int)),150),2)
    line([(0,104),(1024,104)],(*tuple(PALE.astype(int)),185),1)
    line([(0,187),(1024,187)],(*tuple(PALE.astype(int)),185),1)
    # Alternating blue and rose inlays sit inside the UV-mapped fabric band.
    for x in range(12,1024,64):
        color=BLUE if (x//64)%2==0 else PINK
        cx=x*s;cy=148*s
        diamond=[(cx,cy-12*s),(cx+11*s,cy),(cx,cy+12*s),(cx-11*s,cy)]
        d.polygon(diamond,fill=(*tuple(color.astype(int)),255))
        d.line([diamond[0],diamond[1],diamond[2]],fill=(*tuple(PALE.astype(int)),245),width=2*s)
        d.line([(cx-13*s,130*s),(cx-5*s,121*s),(cx+4*s,121*s),(cx+13*s,130*s)],
               fill=(*tuple(GOLD.astype(int)),205),width=2*s)
        d.line([(cx-13*s,166*s),(cx-5*s,175*s),(cx+4*s,175*s),(cx+13*s,166*s)],
               fill=(*tuple(GOLD.astype(int)),205),width=2*s)
    # Fine interlaced running stitches give the edge a textile finish.
    for x in range(0,1024,18):
        col=(252,241,220,180) if (x//18)%2==0 else (87,190,230,180)
        line([(x,96),(x+7,103),(x+13,96)],col,1.3)
        line([(x+5,184),(x+12,177),(x+18,184)],col,1.3)
    # One BLG stitch mark is centered on the ring. It uses the project patch's
    # lettering and pink bar in a single repeat.
    cx,cy=512*s,148*s
    for sign, shade in ((-1,BLUE),(1,PINK)):
        diamond=[(cx+sign*x*s,cy+y*s) for x,y in ((23,0),(41,-17),(60,0),(41,17))]
        d.polygon(diamond,fill=(*tuple(shade.astype(int)),235),outline=(255,224,176,242),width=2*s)
        d.line((diamond[0],diamond[1],diamond[2]),fill=(255,247,231,242),width=2*s)
    crest=[(cx,cy-26*s),(cx+35*s,cy),(cx,cy+26*s),(cx-35*s,cy)]
    d.polygon(crest,fill=(41,79,113,225),outline=(*tuple(GOLD.astype(int)),255),width=2*s)
    logo=blg_wordmark(49*s, True)
    im.alpha_composite(logo,(cx-logo.width//2,cy-logo.height//2))
    # Seam the texture by repeating both ends.
    first=im.crop((0,0,28*s,256*s))
    last=im.crop(((1024-28)*s,0,1024*s,256*s))
    im.alpha_composite(first,((1024-28)*s,0))
    im.alpha_composite(last,(0,0))
    im=im.resize(size,Image.Resampling.LANCZOS)
    im.save(ART/'w_outer_braid.png',optimize=True)


def corner_texture(source_name,output_name,glow=False):
    original=game_texture(STOCK/(source_name+'.tex'))
    alpha=np.asarray(original.getchannel('A'),dtype=np.float32)
    h,w=alpha.shape
    u=(np.arange(w)+.5)/w
    v=(np.arange(h)+.5)/h
    x,y=np.meshgrid(u,v)
    # The game mesh's UV island is already a curled thread path. Keep its
    # exact silhouette and place alternating crystal color along the path.
    blend=np.clip((.5+.5*np.sin(x*math.tau*4+.25)),0,1)[...,None]
    weave=BLUE[None,None,:]*(1-blend)+PINK[None,None,:]*blend
    highlight=np.clip((alpha/255*1.8)[...,None],0,1)
    rgb=weave*(1-highlight*.38)+PALE*highlight*.38
    # A warm metallic subthread alternates along the two broad sections.
    metal=np.exp(-((y-(.91-.8*x))/.021)**2)*np.clip(alpha/160,0,1)
    rgb=rgb*(1-metal[...,None]*.67)+GOLD*metal[...,None]*.67
    if glow:
        alpha=np.minimum(alpha*1.12,255)
        rgb=np.clip(rgb*1.07+6,0,255)
    else:
        alpha=np.minimum(alpha*1.65,255)
    arr=np.uint8(np.dstack((np.clip(rgb,0,255),alpha)))
    Image.fromarray(arr,'RGBA').save(ART/(output_name+'.png'),optimize=True)


def mistfield():
    original=game_texture(STOCK/'Generic_GroundBaseLayer.tex').resize((512,512),Image.Resampling.LANCZOS)
    src=np.asarray(original,dtype=np.float32)
    alpha=src[:,:,3]/255
    yy,xx=np.mgrid[:512,:512]
    radius=np.sqrt(((xx-255.5)/256)**2+((yy-255.5)/256)**2)
    color_t=np.clip((xx/511)*.65+(yy/511)*.30,0,1)[...,None]
    edge=BLUE[None,None,:]*(1-color_t)+PINK[None,None,:]*color_t
    center=PALE[None,None,:]
    mix=np.clip(radius[...,None]*.75,0,.75)
    rgb=center*(1-mix)+edge*mix
    # Broad, low-contrast pearl fields preserve visibility through the zone.
    cloud=(np.sin(xx/34+np.sin(yy/57))*np.sin(yy/46+.6)+1)/2
    rgb=rgb*(.88+.12*cloud[...,None])
    a=np.clip(alpha*0.52*255,0,255)
    im=Image.fromarray(np.uint8(np.dstack((rgb,a))),'RGBA')
    im.save(ART/'w_mistfield.png',optimize=True)


def sewing_glint():
    # A single wrap of the native wall UV. The stitch head runs along the upper hem.
    w,h=1024,256
    yy,xx=np.mgrid[:h,:w]
    dx=xx-512.
    dy=yy-96.
    tail=np.exp(np.minimum(dx,0)/39.)*(dx<0)
    thread=tail*np.exp(-(dy/2.7)**2)
    core=np.exp(-(np.abs(dx)/10.+np.abs(dy)/4.5)**1.35)
    bloom=.21*np.exp(-(dx/21.)**2-(dy/9.)**2)
    glint=np.maximum(np.exp(-(dx/1.8)**2-np.abs(dy)/11.),np.exp(-(dy/1.7)**2-np.abs(dx)/19.))
    alpha=np.clip(thread*.88+core+bloom+glint*.6,0,1)
    rgb=GOLD+(PALE-GOLD)*np.minimum(1.,core+glint)[...,None]
    Image.fromarray(np.uint8(np.dstack((rgb,alpha*255))),'RGBA').save(ART/'w_sewing_glint.png',optimize=True)


def threads():
    w,h=512,128
    u,v=np.meshgrid((np.arange(w)+.5)/w,(np.arange(h)+.5)/h)
    # Long strands flow through the trail UV and remain distinct as they taper.
    wave1=.31+.09*np.sin(2*math.tau*u)
    wave2=.51+.11*np.sin(2*math.tau*u+1.05)
    wave3=.70+.075*np.sin(2*math.tau*u+2.25)
    bands=[]
    for center,width in ((wave1,.085),(wave2,.060),(wave3,.085)):
        bands.append(np.exp(-((v-center)/width)**2))
    blue,pale,pink=bands
    total=np.maximum(blue+pale+pink,1.e-4)
    rgb=(blue[...,None]*BLUE+pale[...,None]*PALE+pink[...,None]*PINK)/total[...,None]
    alpha=np.clip((blue*.72+pale*.54+pink*.76)*255,0,255)
    # Parallel gold sewing points travel between the three silk strands.
    for x in range(16,512,32):
        j=x
        y=wave2[0,j]*h
        alpha[max(0,int(y)-2):min(h,int(y)+3),j-3:j+4]=255
        rgb[max(0,int(y)-2):min(h,int(y)+3),j-3:j+4]=GOLD
    Image.fromarray(np.uint8(np.dstack((rgb,alpha))),'RGBA').save(ART/'w_thread_trail.png',optimize=True)


def badge():
    # Compact badge tile for a center clasp if the runtime icon is not present.
    size=256
    im=Image.new('RGBA',(size,size))
    d=ImageDraw.Draw(im)
    cx=cy=size//2
    d.polygon([(cx,18),(238,cy),(cx,238),(18,cy)],fill=(27,45,68,220),
              outline=(*tuple(GOLD.astype(int)),255),width=5)
    d.polygon([(cx,45),(211,cy),(cx,211),(45,cy)],fill=(93,170,226,185),
              outline=(247,238,227,245),width=3)
    d.polygon([(cx,68),(cx+68,cy),(cx,188),(cx-68,cy)],fill=(42,116,188,238))
    d.polygon([(cx,68),(cx+68,cy),(cx,128),(cx-68,cy)],fill=(235,99,177,225))
    panel=[(cx-75,cy-28),(cx-62,cy-41),(cx+62,cy-41),(cx+75,cy-28),
           (cx+75,cy+28),(cx+62,cy+41),(cx-62,cy+41),(cx-75,cy+28)]
    d.polygon(panel,fill=(27,45,68,235),outline=(*tuple(GOLD.astype(int)),255),width=3)
    logo=blg_wordmark(132,True)
    im.alpha_composite(logo,(cx-logo.width//2,cy-logo.height//2))
    d.line([(97,168),(152,168)],fill=(*tuple(GOLD.astype(int)),250),width=5)
    im.save(ART/'w_blg_clasp.png',optimize=True)


def blg_wordmark(width,pink_bar=True,color=(249,247,239)):
    """The traced, perspective-corrected BLG tournament flag lettering."""
    paths=[
        [(78,145),(102,120),(123,123),(113,115),(169,56),(168,43),(210,52),(208,59),
         (144,122),(213,135),(243,106),(239,97),(216,93),(232,78),(221,73),(232,64),
         (219,55),(298,67),(272,96),(275,124),(229,167)],
        [(242,169),(318,83),(318,69),(361,75),(301,149),(377,155),(380,189)],
        [(381,110),(419,116),(425,167),(470,176),(468,157),(457,153),(455,139),
         (503,148),(507,218),(390,191)],
        [(372,76),(493,91),(499,122),(377,105)],
    ]
    image=Image.new('RGBA',(width,round(width*.34)))
    draw=ImageDraw.Draw(image)
    for i,points in enumerate(paths):
        xy=[((x-76)/435*width,(y-41-.167*(x-170))/145*image.height) for x,y in points]
        fill=(255,152,215,255) if i==3 and pink_bar else (*color,255)
        draw.polygon(xy,fill=fill)
    return image


if __name__=='__main__':
    uv_strip()
    corner_texture('Generic_WIndicator_Corner_FirstNew','w_corner_gem')
    corner_texture('Generic_WIndicator_Corner_FirstNew_Overlay','w_corner_glint',True)
    mistfield()
    sewing_glint()
    threads()
    badge()
