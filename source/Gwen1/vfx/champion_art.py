"""BLG's projected wordmark, cut-glass particles and the two sides of Gwen's snip."""
from pathlib import Path
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ART = Path(__file__).resolve().parent / 'art'
ICE = (58, 185, 255)
ROSE = (253, 92, 186)
GOLD = (255, 213, 150)
PEARL = (255, 251, 237)


def gem(name, base, point=False):
    size = 256
    im = Image.new('RGBA', (size, size))
    glow = Image.new('RGBA', im.size)
    ImageDraw.Draw(glow).ellipse((91,66,165,190), fill=(*base,145))
    im = Image.alpha_composite(im, glow.filter(ImageFilter.GaussianBlur(15)))
    d = ImageDraw.Draw(im)
    top, right, bottom, left = (144,17), (169,115), (108,224), (86,130)
    ridge, lower = (133,95), (114,165)
    shadow = tuple(int(x*.47) for x in base)
    pale = tuple((x+255)//2 for x in base)
    for pts,col in [([top,ridge,left],pale),([top,right,ridge],PEARL),
                    ([right,lower,ridge],base),([left,ridge,lower],base),
                    ([left,lower,bottom],shadow),([lower,right,bottom],pale)]:
        d.polygon(pts, fill=(*col,246))
    d.line([top,left,bottom,right,top], fill=(*GOLD,238), width=3)
    d.line([top,ridge,lower], fill=(*PEARL,255), width=3)
    # A softly tapered glimmer trails the long axis of each turning facet.
    tail = Image.new('RGBA',im.size)
    tr=ImageDraw.Draw(tail)
    tr.polygon([(111,160),(117,176),(86,252)],fill=(*base,105))
    tr.line([(142,38),(159,13)],fill=(*PEARL,104),width=2)
    im=Image.alpha_composite(tail,im)
    d=ImageDraw.Draw(im)
    if point:
        d.polygon([(128,27),(138,113),(209,127),(139,136),(124,229),(116,137),
                   (44,127),(116,117)], fill=(*GOLD,241))
        d.polygon([(128,60),(133,122),(177,127),(132,131),(124,186),(122,131),
                   (77,127),(122,122)],fill=(*PEARL,255))
    im.resize((128,128),Image.Resampling.LANCZOS).save(ART/f'{name}.png')


def seal():
    from w_art import blg_wordmark
    im = Image.new('RGBA',(1024,512))
    d = ImageDraw.Draw(im)
    # Open laurel-like edges leave negative space around the three letters.
    for sign, col in ((-1,ICE),(1,ROSE)):
        def pts(poly):
            return [(512+sign*x,y) for x,y in poly]
        d.polygon(pts([(205,371),(310,343),(454,183),(408,279),(318,354)]),
                  fill=(*col,201))
        d.line(pts([(170,393),(313,366),(467,191)]),fill=(*GOLD,235),width=4)
        d.line(pts([(348,324),(445,273),(475,245)]),fill=(*PEARL,218),width=3)
        d.polygon(pts([(326,338),(355,286),(349,317),(372,302)]),fill=(*PEARL,232))
        d.line(pts([(31,383),(108,380),(191,362)]),fill=(*GOLD,231),width=4)
    d.polygon([(512,361),(529,379),(512,401),(495,379)],fill=(*GOLD,255))
    d.polygon([(512,367),(519,377),(512,390),(505,378)],fill=(*PEARL,255))
    mask = blg_wordmark(665).getchannel('A')
    alpha = Image.new('L',im.size)
    alpha.paste(mask,((1024-mask.width)//2,129))
    outline = alpha.filter(ImageFilter.MaxFilter(13))
    gl = Image.new('RGBA',im.size,(46,182,247,0)); gl.putalpha(outline.filter(ImageFilter.GaussianBlur(12)).point(lambda a:a*.65))
    im=Image.alpha_composite(gl,im)
    dark=Image.new('RGBA',im.size,(19,37,66,0)); dark.putalpha(outline); im=Image.alpha_composite(im,dark)
    ys,xs=np.mgrid[:512,:1024]
    # Pearl cap and turquoise foil below it. The pink bar identifies the BLG mark.
    t=np.clip((ys-164)/143,0,1)[...,None]
    rgb=np.array((247,254,255))*(1-t)+np.array((68,197,250))*t
    pink=(xs>610)&(ys<195)
    rgb[pink]=np.array((255,141,207))
    letters=Image.fromarray(np.uint8(np.dstack((rgb,np.asarray(alpha)))))
    im=Image.alpha_composite(im,letters)
    im.resize((512,256),Image.Resampling.LANCZOS).save(ART/'w_blg_wordmark.png')


def currents():
    h,w=256,1024
    y,x=np.mgrid[:h,:w]
    u=(x+.5)/w
    for name,base in [('ice',ICE),('rose',ROSE)]:
        intensity=np.zeros((h,w))
        for start,span,level in ((.02,.25,1.),(.54,.17,.75)):
            t=(u-start)/span
            valid=(t>=0)&(t<=1)
            tail=np.clip(t,0,1)**.7
            center=138-35*np.sin(np.pi*np.clip(t,0,1))+(6 if name=='rose' else -6)
            bend=(1-tail)*14*np.sin(t*7)
            rope=np.exp(-((y-center)/3.8)**2)+.5*np.exp(-((y-center-bend-7)/2.)**2)
            # A sheer folded veil follows each needle. Its fine diagonal seams
            # alternate with an unpainted opening in the wall.
            depth=13+35*np.sin(np.pi*np.clip(t,0,1))**1.7
            cloth=(y-center)/depth
            folds=np.clip(1-abs(((t*9+cloth*.64)%1)-.5)*2,0,1)
            veil=(cloth>0)&(cloth<1)
            gauze=veil*np.sin(np.pi*np.clip(cloth,0,1))*(.18+.24*folds**2)*np.sin(np.pi*np.clip(t,0,1))
            hem=np.exp(-((cloth-.87)/.05)**2)*.52*np.sin(np.pi*np.clip(t,0,1))
            head=np.exp(-((t-.94)/.035)**2-((y-center)/13)**2)
            spark=np.exp(-((t-.94)/.005)**2-np.abs(y-center)/20)
            intensity=np.maximum(intensity,valid*(rope*tail+head+spark+gauze+hem))
        alpha=np.clip(intensity,0,1)
        rgb=np.array(base)+(np.array(PEARL)-np.array(base))*np.clip((intensity-.50)*1.1,0,1)[...,None]
        Image.fromarray(np.uint8(np.dstack((rgb,alpha*255)))).save(ART/f'w_current_{name}.png')


def shear_strokes():
    """The same two authored RGBA maps drive the native cast and review renderer."""
    h=w=256
    y,x=np.mgrid[:h,:w]; u=(x+.5)/w; v=(y+.5)/h
    for name,base,accent in [('open',ICE,ROSE),('close',ROSE,ICE)]:
        a=u if name=='open' else 1-u
        window=np.sin(np.pi*np.clip(a,0,1))**.52
        hem=.19+.12*a+.035*np.sin(2*np.pi*a)
        taper=.11*np.sin(np.pi*a)**.7+.009
        d=(v-hem)/taper
        body=np.clip(1-abs(d),0,1)**.8 * window
        edge=np.exp(-((v-hem+taper*.45)/.014)**2)*window
        strand=np.exp(-((v-hem-.12-.025*np.sin(a*14))/.010)**2)*window
        facets=np.clip(1-abs((a*12+v*3)%1-.5)*2,0,1)
        stitch=np.exp(-((v-hem-.19)/.012)**2)*np.clip(np.cos(a*72),0,1)**2*window
        haze=np.exp(-(d/1.9)**2)*window*.19
        alpha=np.clip(body*.9+edge+strand*.86+stitch*.95+haze,0,1)
        rgb=np.broadcast_to(np.array(base,dtype=float),(h,w,3)).copy()
        bright=np.clip(body*(.15+.65*facets)+edge*.93,0,1)[...,None]
        rgb=rgb*(1-bright)+np.array(PEARL)*bright
        rgb=np.where((strand>.14)[...,None],np.array(accent)*.64+np.array(PEARL)*.36,rgb)
        rgb=np.where((stitch>.15)[...,None],np.array(GOLD),rgb)
        Image.fromarray(np.uint8(np.dstack((rgb,alpha*255)))).save(ART/f'q_cast_{name}.png')


def victory_flash():
    n=512
    im=Image.new('RGBA',(n,n)); d=ImageDraw.Draw(im)
    for i in range(12):
        a=math.pi*i/6+.16
        length=[247,123,157,192,156,120][i%6]
        width=8 if i%3==0 else 3
        def xy(rad,off=0):
            return (256+rad*math.cos(a)-off*math.sin(a),256+rad*math.sin(a)+off*math.cos(a))
        col=(ICE,PEARL,ROSE,GOLD)[i%4]
        d.polygon([xy(22),xy(46,width),xy(length),xy(52,-width)],fill=(*col,226))
        d.line([xy(34),xy(length*.84)],fill=(*PEARL,245),width=2)
    vertices=[(256,134),(306,248),(256,376),(204,254)]
    d.polygon(vertices,fill=(*GOLD,255))
    for poly,col in [([(256,149),(246,242),(213,253)],ICE), ([(256,149),(296,248),(246,242)],PEARL),
                     ([(246,242),(296,248),(256,358)],ROSE), ([(213,253),(246,242),(256,358)],(168,223,255))]:
        d.polygon(poly,fill=(*col,254))
    for r in (69,81):
        for start in (20,110,200,290):
            d.arc((256-r,256-r,256+r,256+r),start,start+41,fill=(*GOLD,214),width=3)
    blur=im.filter(ImageFilter.GaussianBlur(11))
    Image.alpha_composite(blur,im).resize((256,256),Image.Resampling.LANCZOS).save(ART/'q_final_star.png')


def silk_cut(name,base):
    h,w=256,512
    y,x=np.mgrid[:h,:w];u=(x+.5)/w;v=(y+.5)/h
    taper=np.sin(np.pi*u)**.64
    spine=.5+.16*np.sin(np.pi*(u-.13))-.11*u
    thickness=.008+.091*taper*(.65+.35*np.cos(u*6))
    cross=(v-spine)/thickness
    fill=np.clip(1-abs(cross),0,1)**.64*taper
    ridge=np.exp(-((cross+.41)/.14)**2)*taper
    facets=np.abs(((u*8+cross*.24)%1)*2-1)
    ribbon=np.exp(-((v-spine-.08*np.sin(np.pi*u)-.034)/.008)**2)*taper
    gold=np.exp(-((v-spine+.12*np.sin(np.pi*u))/.006)**2)*taper
    alpha=np.clip(fill*.88+ridge+ribbon*.78+gold*.81,0,1)
    tint=np.minimum(1,ridge+fill*facets*.61)[...,None]
    rgb=np.array(base)*(1-tint)+np.array(PEARL)*tint
    rgb=np.where((gold>.12)[...,None],np.array(GOLD),rgb)
    Image.fromarray(np.uint8(np.dstack((rgb,alpha*255)))).save(ART/f'q_silk_{name}.png')


def blade_wake():
    h,w=128,512
    y,x=np.mgrid[:h,:w];u=(x+.5)/w;v=(y+.5)/h
    width=.17+.34*u
    core=(v-.56)/width
    fill=np.exp(-core**2*1.8)*u**1.3
    filament=np.exp(-((v-.76+.12*np.sin(u*4))/.019)**2) * u**.80
    stitch=np.exp(-((v-.28-.16*u)/.017)**2)*np.clip(np.cos(u*36),0,1)**2*u
    a=np.minimum(.86,.48*fill+filament*.63+stitch*.55)*np.sin(np.pi*v)**.4
    rgb=np.broadcast_to((246,252,255),(h,w,3)).copy()
    rgb[stitch>.2]=GOLD
    Image.fromarray(np.uint8(np.dstack((rgb,a*255)))).save(ART/'q_blade_stitch.png')


def lace():
    n=1024; mid=n/2
    im=Image.new('RGBA',(n,n)); d=ImageDraw.Draw(im)
    def pos(a,r):
        return (mid+r*math.cos(a),mid+r*math.sin(a))
    for i in range(6):
        a=i*math.tau/6+.18
        for j,(base,width) in enumerate(((ICE,4),(GOLD,2),(ROSE,3))):
            steps=np.linspace(0,1,100)
            path=[pos(a+t*.87, 401-32*math.sin(t*math.pi)**1.2+j*7 + 14*math.sin(t*math.pi*2+j*.55)) for t in steps]
            d.line(path,fill=(*base, (146,182,118)[j]),width=width)
        for t in range(8):
            angle=a+.085+t*.082
            x,y=pos(angle,426)
            d.ellipse((x-2,y-2,x+2,y+2),fill=(*PEARL,167))
        x,y=pos(a,401); ux,uy=math.cos(a),math.sin(a)
        def at(r,k):return (x+ux*r-uy*k,y+uy*r+ux*k)
        outer=[at(22,0),at(0,11),at(-19,0),at(0,-11)]
        d.line(outer+[outer[0]],fill=(*GOLD,210),width=3)
        d.polygon([at(10,0),at(0,5),at(-8,0),at(0,-5)],fill=(*(ICE if i%2 else ROSE),191))
    im.resize((512,512),Image.Resampling.LANCZOS).save(ART/'w_stitch_orbit.png')


def paint():
    for name,col in [('ice',ICE),('rose',ROSE),('gold',GOLD)]:
        gem('blg_crystal_'+name,col,name=='gold')
    seal()
    currents()
    blade_wake()
    lace()
    silk_cut('ice',ICE)
    silk_cut('rose',ROSE)
    shear_strokes()
    victory_flash()


if __name__=='__main__':
    paint()
