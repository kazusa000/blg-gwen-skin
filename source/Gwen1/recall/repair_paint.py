"""Paint diffuse value groups and build particle masks for the game materials."""
from io import BytesIO
import json
import struct
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from core import GW, SKIN, WORK
from build_qw import encode_tex, check_tex

ART = GW/'vfx/art'



def bitmap(a):
    return Image.fromarray(np.rint(np.clip(a,0,255)).astype('uint8'))


def dye(array, stops, colors, chroma):
    rgb=np.asarray(array).astype('f')
    value=rgb@np.array([.245,.625,.13],dtype='f')
    tone=np.stack([np.interp(value,stops,col) for col in np.array(colors).T],-1)
    return tone+(rgb-value[...,None])*chroma


def doll():
    # Paint in the UV rectangles of the shipped marionettes (spherical face, fabric trims and cape).
    from importlib.util import spec_from_file_location,module_from_spec
    spec=spec_from_file_location('plush_uv',GW/'plush_2233/atlas.py')
    palette=module_from_spec(spec);spec.loader.exec_module(palette)
    img=Image.open(palette.ATLAS).convert('RGB')
    for i,(name,rect) in enumerate(palette.RECT.items()):
        x,y,w,h=rect
        tile=np.asarray(img.crop((x,y,x+w,y+h))).astype('f')
        v,u=np.mgrid[0:h,0:w];u=(u+.5)/w;v=(v+.5)/h
        roll=.5+.5*np.cos(2*np.pi*(u-.47))
        if name.startswith('face'):
            cheeks=np.maximum(*[np.exp(-((u-c)/.052)**2-((v-.62)/.075)**2) for c in (.38,.62)])
            diffuse=.84+.13*roll-.072*v+.055*np.exp(-((v-.46)/.25)**2)
            grain=1.9*np.cos(u*w*.75+v*h*.25)+1.1*np.sin(v*h*1.25)
            tile=diffuse[...,None]*[247,217,192]+cheeks[...,None]*[7,-28,-17]+grain[...,None]
            face=bitmap(tile);pen=ImageDraw.Draw(face)
            def box(cx,cy,rx,ry):return (int((cx-rx)*w),int((cy-ry)*h),int((cx+rx)*w),int((cy+ry)*h))
            for sign in (-1,1):
                u0=.50+sign*.087;v0=.514;rx=.030
                if name=='face22':
                    ry=.080
                    pen.ellipse(box(u0,v0,rx+.004,ry+.006), fill=(64,39,56))
                    pen.ellipse(box(u0,v0+.009,rx-.003,ry-.011),fill=(134,57,81))
                    pen.ellipse(box(u0-.002,v0-.002,.011,.044),fill=(73,42,69))
                    pen.ellipse(box(u0+.001,v0+.044,.014,.014),fill=(192,104,115))
                    pen.ellipse(box(u0-.010,v0-.028,.008,.014),fill=(249,224,207))
                    pen.line([(int((u0-.029)*w),int((v0-ry+.008)*h)),(int((u0+.029)*w),int((v0-ry+.001)*h))],
                             fill=(72,44,65),width=5)
                else:
                    # Half-lidded oval: keep a horizontal stitched upper lid and
                    # show most of the rounded rose iris beneath it.
                    top=v0-.004;height=.082;outer=.036;inner=.029
                    def sleepy_shape(cx,rx_,y0,h_,color):
                        # A flat satin lid over a smoothly rounded lower oval.
                        arc=[(cx+rx_*np.cos(t),y0+h_*np.sin(t))
                             for t in np.linspace(0,np.pi,25)]
                        pts=[(cx-rx_,y0),(cx+rx_,y0),*arc]
                        pen.polygon([(int(x*w),int(y*h)) for x,y in pts],fill=color)
                    sleepy_shape(u0,outer,top,height,(75,39,57))
                    sleepy_shape(u0,inner,top+.008,height-.014,(163,68,96))
                    pen.ellipse(box(u0,top+.056,.013,.021),fill=(82,39,66))
                    pen.ellipse(box(u0-.010,top+.041,.005,.007),fill=(250,225,211))
                    lid_y=int(top*h)
                    pen.line([(int((u0-.037)*w),lid_y),(int((u0+.037)*w),lid_y)],
                             fill=(75,39,57),width=7)
                for k in range(3):
                    dx=.378 if sign<0 else .606;cx=dx+k*.009
                    pen.line([(cx*w,.63*h),((cx+.004)*w,.61*h)],fill=(202,126,124),width=2)
            if name=='face22':
                pen.ellipse(box(.50,.628,.026,.033),fill=(111,51,68))
                pen.ellipse(box(.501,.642,.015,.010),fill=(203,117,126))
            else:
                pen.line([(int(.489*w),int(.621*h)),(int(.511*w),int(.621*h))],
                         fill=(105,65,78),width=5)
            img.paste(face,(x,y))
            continue
        elif name in ('pin_blue','pin_rose'):
            base=np.array(palette.COLORS[name],dtype='f')
            facets=np.where((u+v)<.48,1.18,np.where((u-v)>.08,.82,
                    np.where((v-u)>.08,1.04,.66)))
            glint=np.exp(-((u-.28)/.08)**2-((v-.20)/.10)**2)
            tile=base[None,None,:]*facets[...,None]+glint[...,None]*[90,78,64]
            tile=np.clip(tile,0,255)
            facet=bitmap(tile);pen=ImageDraw.Draw(facet)
            pen.line((int(.08*w),int(.84*h),int(.86*w),int(.10*h)),fill=(239,232,227),width=3)
            img.paste(facet,(x,y))
            continue
        elif name=='badge':
            tile=tile*[.83,.84,.90]
        else:
            fold=.5+.5*np.cos(2*np.pi*(u+.04*np.sin(3*v))*4)
            value=.69+.15*roll+.11*(1-v)+.043*fold
            if name in ('blue','blue_mid','blue_lit','ice','ice_lit','ice_shadow'):
                value+=.12*np.exp(-((u-.42+.045*np.sin(5*v))/.17)**2)
            tile=tile*value[...,None]+(1-roll[...,None])*[0,1,6]
            if name in ('navy','ivory','rose','azure'):
                # Two rows of running stitch and picot edging read even on the short cape.
                seam=np.exp(-((v-.88)/.019)**2)*(.3+.7*(np.cos(2*np.pi*u*24)>.0))
                tile=tile*(1-.44*seam[...,None])+np.array([206,180,160])*.44*seam[...,None]
        img.paste(bitmap(tile),(x,y))
    return img


def particle(name):
    im=Image.open(ART/(name+'.png')).convert('RGBA')
    src=np.asarray(im).astype('f')/255
    h,w=src.shape[:2];y,x=np.mgrid[0:h,0:w]
    # Continuous meshes wrap in U. Billboards and one-shot trails need a gutter on all four edges.
    wraps=name in {'w_outer_braid','w_current_ice','w_current_rose','w_sewing_glint'}
    dist=np.minimum(y,h-1-y)/h
    if not wraps: dist=np.minimum(dist,np.minimum(x,w-1-x)/w)
    edge=np.clip((dist-.016)/.07,0,1);edge=edge**2*(3-2*edge)
    a=src[...,3]*edge
    if name=='e_blade_facets':
        # Concentrate the animated reflection on a narrow band of the blade UV.
        v=(y+.5)/h
        a*=np.exp(-((v-.5)/.30)**4)
    gain={'w_mistfield':.65,'w_corner_glint':.73,'w_outer_braid':.82,'e_blade_facets':.78}.get(name,.87)
    a=np.where(a<2/255,0,np.clip(a*gain,0,1))
    rgb=src[:,:,:3]*np.power(a[...,None],.82)
    rgb*=np.array([.91,.93,.98])
    return bitmap(np.dstack([rgb,a])*255)


def encode_particle(im):
    # Resize the channels independently: PIL's RGBA resize normally unpremultiplies them.
    # Store exact channels so subpixel transparent gutters cannot pick up BC endpoint colours.
    w,h=im.size
    levels=[]
    while True:
        raw=np.asarray(im)
        assert not np.any(raw[raw[...,3]==0,:3])
        levels.append(raw[:,:,[2,1,0,3]].tobytes())
        if im.size==(1,1):break
        size=(max(1,im.width//2),max(1,im.height//2))
        channels=[c.resize(size,Image.Resampling.BOX) for c in im.split()]
        im=Image.merge('RGBA',channels)
        buf=np.array(im);buf[buf[...,3]==0,:3]=0
        im=Image.fromarray(buf)
    return struct.pack('<4sHH4B',b'TEX\0',w,h,1,20,0,1)+b''.join(reversed(levels))


def decode_full(raw):
    w,h=struct.unpack_from('<HH',raw,4)
    if raw[9]==20:
        return Image.frombytes('RGBA',(w,h),raw[-w*h*4:],'raw','BGRA')
    assert raw[9]==12
    template=BytesIO();Image.new('RGBA',(4,4)).save(template,'DDS',pixel_format='DXT5')
    header=bytearray(template.getvalue()[:128])
    n=16*((w+3)//4)*((h+3)//4)
    struct.pack_into('<III',header,12,h,w,n)
    return Image.open(BytesIO(header+raw[-n:])).convert('RGBA')

