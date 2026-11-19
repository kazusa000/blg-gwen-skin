"""Shared atlas and bind-space cloth, embroidery threads, cup, and stage geometry."""
from core import *
from PIL import Image,ImageDraw,ImageFont
from io import BytesIO
import struct, math
TAU=2*np.pi
TINT=[(67,182,242),(240,131,187),(91,195,243),(239,132,187)]
FONT='C:/Windows/Fonts/arialbd.ttf'
def source(name):
    data=(WORK/(name+'.tex')).read_bytes();w,h=struct.unpack_from('<HH',data,4)
    b=BytesIO();Image.new('RGBA',(4,4)).save(b,format='DDS',pixel_format='DXT5')
    head=bytearray(b.getvalue()[:128]);n=((w+3)//4)*((h+3)//4)*16
    struct.pack_into('<III',head,12,h,w,n)
    return Image.open(BytesIO(head+data[-n:])).convert('RGBA')
def bezier(points):
    p=np.array(points);t=np.linspace(0,1,38)[:,None]
    return (1-t)**3*p[0]+3*(1-t)**2*t*p[1]+3*(1-t)*t*t*p[2]+t**3*p[3]
def logo(team):
    if team!='HLE':
        return Image.open(GW/'inputs/badges'/('badge_'+team+'.png')).convert('RGBA')
    # Trace the three embroidered arcs in the stock HLE crest, without the Worlds 2021 border.
    im=Image.new('RGBA',(480,224));d=ImageDraw.Draw(im)
    arcs=[((97,101),(130,103),(160,112),(187,137),(177,145),(151,123),(124,107),(97,101),'#ff800c'),
          ((76,110),(99,104),(126,108),(149,124),(141,128),(119,117),(103,115),(87,124),'#414754'),
          ((67,149),(83,130),(110,122),(137,129),(131,140),(106,128),(85,132),(67,149),'#aab6c3')]
    for a,b,c,e,f,g,h,j,color in arcs:
        points=np.vstack((bezier([a,b,c,e]),bezier([f,g,h,j])))
        d.polygon([tuple(x) for x in (points-[67,98])*4],fill=color)
    return im.crop(im.getbbox())
def badge(team):
    em=logo(team)
    if team=='DK':
        # The source lockup includes a small sponsor wordmark below the team symbol.
        alpha=np.asarray(em.getchannel('A'))
        occupied=(alpha>64).any(axis=1)
        gaps=np.where(~occupied & (np.arange(len(occupied))>len(occupied)*.55))[0]
        if len(gaps):em=em.crop((0,0,em.width,int(gaps[0])))
    w=246;h=round(w*em.height/em.width)
    em=em.resize((w,h),Image.Resampling.LANCZOS)
    im=Image.new('RGBA',(256,256))
    im.alpha_composite(em,((256-w)//2,(256-h)//2))
    im.save(WORK/('badge_'+team+'.png'))
def art():
    for n in TEAM:badge(n)
    y,x=np.mgrid[-1:1:256j,-1:1:256j]
    r=x*x+y*y
    core=np.exp(-r*65)
    rays=np.maximum(np.exp(-abs(x)*42-abs(y)*4.8),np.exp(-abs(y)*45-abs(x)*5.4))
    halo=.30*np.exp(-r*8)+.58*rays+.52*core
    rgb=np.stack((.47+.45*(x+1)/2+.32*core,.66+.22*(1-x)/2+.23*core,.98+0*x),axis=2)
    Image.fromarray(np.uint8(255*np.clip(np.dstack((rgb,halo*(1-np.minimum(r,1))**2)),0,1))).save(WORK/'flash.png')
    sheet=Image.new('RGB',(1024,1024),'#ede2cb')
    # Painted metal reflections keep the turned silver and the deep interior readable at game scale.
    for i,col in enumerate(((169,191,218),(187,208,229),(139,157,180),(29,52,90),(217,191,146),(97,171,210))):
        t,u=np.mgrid[0:64,0:512];u=u/511;t=t/63
        angle=TAU*(u+.04*t)
        shine=.81+.16*np.cos(2*angle)+.19*np.cos(5*angle-.9)+.10*np.cos(7*angle)
        fine=np.maximum(0,np.cos(9*angle+.43))**18
        if i==2:shine=(.51+.58*(1-t))*(.92+.13*np.cos(3*angle-.5)+.08*np.cos(8*angle))
        rgb=np.clip(np.array(col)[None,None,:]*shine[:,:,None]+fine[:,:,None]*(14 if i==2 else 33),0,255)
        sheet.paste(Image.fromarray(rgb.astype('uint8')),(0,64*i))
    d=ImageDraw.Draw(sheet)
    colors=['#f1c77f','#cbeeff','#45b9e9','#fa92c2','#f4e8d9','#263954','#9e6d48','#6285ac']
    for i,c in enumerate(colors):d.rectangle((520+i*61,4,578+i*61,110),fill=c)
    for i,(team,tint) in enumerate(zip(TEAM,TINT)):
        yy=128+i*170
        rng=np.random.default_rng(20+i)
        H,W=158,488;y,x=np.mgrid[:H,:W];shade=.82+.15*np.sin(x/W*np.pi)+.04*np.cos(y*.11)+.03*np.sin((x+y)*.72)+rng.normal(0,.012,(H,W))
        base=np.array(tint)*.74+np.array([21,25,47])*.26
        tile=Image.fromarray(np.uint8(np.clip(shade[:,:,None]*base[None,None,:],0,255)))
        pen=ImageDraw.Draw(tile)
        for j in (7,H-9):
            pen.line((0,j,W,j),fill='#f2d5a3',width=5)
            for k in range(0,W,18):pen.line((k,j+4,k+8,j+4),fill='#f4e3c8',width=2)
        for k in range(35,W,69):
            pen.polygon([(k,56),(k+5,74),(k+16,79),(k+5,84),(k,103),(k-5,84),(k-16,79),(k-5,74)],outline='#f0d0a2',width=2)
        sheet.paste(tile,(528,yy))
    plaque=Image.new('RGB',(490,164),'#203148');pen=ImageDraw.Draw(plaque)
    pen.rounded_rectangle((4,5,486,159),radius=12,outline='#efcd91',width=7)
    blg=logo('BLG');blg.thumbnail((193,97));plaque.paste(blg,(32,(164-blg.height)//2),blg)
    pen.text((344,82),'S16',anchor='mm',font=ImageFont.truetype(FONT,78),fill='#f4d39b')
    sheet.paste(plaque,(523,846));sheet.save(WORK/'atlas.png')
def uv(rect,u,v):
    x,y,w,h=rect
    return [(x+2+u*(w-4))/1024,(y+2+v*(h-4))/1024]
def solid(i):return [((550+i*61)/1024),.055]
class Mesh:
    def __init__(self):self.p=[];self.uv=[];self.n=[];self.j=[];self.f=[]
    def surf(self,j,p,f,uvs,normals=None):
        p=np.asarray(p,float);f=np.asarray(f,int)
        if normals is None:
            normals=np.zeros_like(p);area=np.cross(p[f[:,1]]-p[f[:,0]],p[f[:,2]]-p[f[:,0]])
            for k in range(3):np.add.at(normals,f[:,k],area)
            normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-9)
        self.f.extend(f+len(self.p));self.p.extend(p);self.uv.extend(uvs);self.n.extend(normals);self.j.extend([j]*len(p))
    def tube(self,j,path,r,c,sides=6):
        path=np.asarray(path);tan=np.gradient(path,axis=0);tan/=np.maximum(1e-8,np.linalg.norm(tan,axis=1)[:,None])
        v=np.cross(tan,[0,1,0]);bad=np.linalg.norm(v,axis=1)<.01;v[bad]=np.cross(tan[bad],[1,0,0]);v/=np.linalg.norm(v,axis=1)[:,None]
        w=np.cross(tan,v);a=np.arange(sides)*TAU/sides
        norm=v[:,None]*np.cos(a)[None,:,None]+w[:,None]*np.sin(a)[None,:,None]
        pts=(path[:,None]+r*norm).reshape(-1,3)
        faces=[]
        for k in range(len(path)-1):
            for i in range(sides):
                a=k*sides+i;b=k*sides+(i+1)%sides
                faces.extend(((a,b,b+sides),(a,b+sides,a+sides)))
        self.surf(j,pts,faces,[solid(c)]*len(pts),norm.reshape(-1,3))
def build():
    art();m=Mesh()
    from recall_cup import sculpt
    sculpt(m,uv,solid)
    plaque=np.array([[-17,5.0,29.3],[17,5.0,29.3],[17,14,29.3],[-17,14,29.3]])
    m.surf('Cup',plaque,[(0,1,2),(0,2,3)],[uv((523,846,490,164),a,b) for a,b in [(0,1),(1,1),(1,0),(0,0)]])
    # Ground embroidery leaves the dolls and trophy free of overlapping geometry.
    for r,c in [(105,7),(109,0)]:
        t=np.linspace(0,TAU,65);m.tube('Stage',np.stack([r*np.sin(t),np.full_like(t,1.5),r*np.cos(t)],1),.66,c,5)
    for j,(team,anchor) in enumerate(zip(TEAM,ANCHORS)):
        d=inward(anchor);side=unit(np.cross([0,1,0],d))
        width_axis=unit(np.cross(d,unit([0,.83,1])))
        if width_axis[1]<0:width_axis=-width_axis
        def flagpoint(u,v):
            # Width is partly vertical so the hem and diagonal tear read from above.
            edge=(v-.5)*2*(22.4*(1-.26*u))
            # A short fork and rolled edges distinguish the textile from a flat strip.
            notch=1-.11*max(0,1-abs(2*v-1))*u**8
            return d*(LENGTH*u*notch)+width_axis*edge+np.array([0,-21-6*u+5*np.sin(2.9*np.pi*u+v*1.65)*np.sin(np.pi*u),0])
        for half in (0,1):
            pos=[];tex=[];faces=[]
            for x in range(11):
                for y in range(6):
                    v=y/5;split=.47+.16*v+.025*np.sin(v*3*np.pi)
                    u=(split*x/10) if half==0 else split+(1-split)*x/10
                    pos.append(flagpoint(u,v));tex.append(uv((528,128+170*j,488,158),u,v))
            for x in range(10):
                for y in range(5):
                    a=x*6+y;faces.extend([(a,a+1,a+7),(a,a+7,a+6)])
            jn='Tail'+str(j)+str(half)
            m.surf(jn,pos,faces,tex);m.surf(jn,np.array(pos)-[0,.24,0],np.array(faces)[:,::-1],tex)
        tip=anchor+d*(LENGTH*.56);target=np.array([(-1 if anchor[0]<0 else 1)*21,85,(-1 if anchor[2]<0 else 1)*19])
        for k,col in enumerate((2 if j%2==0 else 3,0)):
            t=np.linspace(0,1,24);path=(target-tip)*t[:,None]
            path+=side*(3*np.sin(t*TAU*1.8+k*np.pi)*np.sin(t*np.pi))[:,None];path[:,1]-=(28-4*k)*np.sin(t*np.pi)
            m.tube('Silk'+str(j),path,.82 if k==0 else .46,col)
    # Faceted four-point stars and two loose split threads mark the instant of each cut.
    def star(j,center,r,c):
        p=[center+[np.cos(k*np.pi/4)*r*(.22 if k%2 else .80),np.sin(k*np.pi/4)*r*(.22 if k%2 else 1),0] for k in range(8)]
        p.extend([center+[0,0,r*.24],center-[0,0,r*.24]])
        f=[tri for k in range(8) for tri in ((8,k,(k+1)%8),(9,(k+1)%8,k))]
        m.surf(j,p,f,[solid(c)]*len(p))
    def flash(key,r):
        # Offset nested stars toward the game camera to keep the pearl core visible.
        star(key,np.array([0.,0,0]),r,2)
        star(key,np.array([0.,1.7,5.5]),r*.72,3)
        star(key,np.array([0.,3.3,9.]),r*.48,4)
        for k,(x,y,scale) in enumerate([(-.84,.47,.20),(.65,.78,.19),(.94,-.21,.16),(-.62,-.72,.14)]):
            star(key,np.array([r*x,r*y,5]),r*scale,2+k%3)
    for j in range(4):
        flash('Dash'+str(j),32)
        key='Burst'+str(j);star(key,np.array([0.,0,0]),16,4)
        for k in range(6):
            a=k*TAU/6+.33;star(key,np.array([22*np.cos(a),16*np.sin(a),5*np.sin(2*a)]),3.2+k%3,2+k%2)
        for k,col in enumerate((2,3)):
            t=np.linspace(0,1,18)
            m.tube(key,np.stack([(2*k-1)*26*t,12*np.sin(t*np.pi)+t*5,(2*k-1)*6*np.sin(t*6)],1),.75,col)
    flash('Change',49)
    return m

