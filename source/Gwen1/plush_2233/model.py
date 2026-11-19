"""Closed, game-scale cloth forms. Coordinates are Gwen bind-space units, Y up."""
import math
import numpy as np
from atlas import uv

TAU=math.tau
SCALE=.77
OFFSETS={22:-9.3,33:9.3}

def part_bone(n,b):
    return f'P{n}_'+('Base' if b=='main' else b)

class Model:
    def __init__(self):
        self.p=[];self.uv=[];self.bones=[];self.tri=[];self.parts=[];self.face_tiles=[]
        self.num=22

    def grid(self,label,tile,bone,rings,vmap=None):
        points=np.asarray(rings,float)
        nr,nc=points.shape[:2]
        start=len(self.p);first=len(self.tri)
        placed=points*SCALE+np.array((OFFSETS[self.num],0,0))
        self.p.extend(placed.reshape(-1,3))
        self.bones.extend([part_bone(self.num,bone)]*(nr*nc))
        for j in range(nr):
            for i in range(nc):
                self.uv.append(uv(tile,i/(nc-1),1-j/(nr-1) if vmap is None else vmap(j/(nr-1))))
        for j in range(nr-1):
            for i in range(nc-1):
                a=start+j*nc+i;b=a+1;d=a+nc;c=d+1
                self.tri.extend(((a,b,c),(a,c,d)))
        self.face_tiles.extend([tile]*(len(self.tri)-first))
        self.parts.append((self.num,label,first,len(self.tri),start,len(self.p)))

    def ell(self,label,tile,bone,center,radii,tilt=0,nu=14,nv=8):
        a=np.linspace(-math.pi,math.pi,nu+1)
        b=np.linspace(-math.pi/2,math.pi/2,nv+1)
        u,v=np.meshgrid(a,b)
        x=radii[0]*np.sin(u)*np.cos(v); y=radii[1]*np.sin(v)
        z=radii[2]*np.cos(u)*np.cos(v)
        co,si=math.cos(tilt),math.sin(tilt)
        self.grid(label,tile,bone,np.stack((x*co-y*si,x*si+y*co,z),axis=-1)+center)

    def tube(self,label,tile,bone,points,width,depth=None,sides=7):
        pts=np.asarray(points,float)
        tg=np.gradient(pts,axis=0);tg/=np.maximum(1e-9,np.linalg.norm(tg,axis=1)[:,None])
        seed=np.array([0.,0.,1.])
        if np.max(abs(tg@seed))>.95:seed=np.array([0.,1.,0.])
        across=np.cross(tg,seed);across/=np.maximum(1e-9,np.linalg.norm(across,axis=1)[:,None])
        front=np.cross(across,tg)
        w=np.broadcast_to(width,len(pts));h=np.broadcast_to(depth if depth is not None else width,len(pts))
        t=np.linspace(0,TAU,sides+1)
        rings=pts[:,None,:]+across[:,None,:]*w[:,None,None]*np.cos(t)[None,:,None]+front[:,None,:]*h[:,None,None]*np.sin(t)[None,:,None]
        rings=np.concatenate((np.repeat(pts[None,:1,:],sides+1,axis=1),rings,np.repeat(pts[None,-1:,:],sides+1,axis=1)))
        self.grid(label,tile,bone,rings[:,::-1])

    def lock(self,label,tile,bone,points,width,depth,stitch=None):
        p=np.asarray(points,float);t=np.linspace(0,1,22)
        path=((1-t)**3)[:,None]*p[0]+(3*(1-t)**2*t)[:,None]*p[1]+(3*(1-t)*t*t)[:,None]*p[2]+(t**3)[:,None]*p[3]
        envelope=.055+np.sin(np.pi*t)**.72*(1.16-.38*t)
        self.tube(label,tile,bone,path,width*envelope,depth*envelope,16)
        if stitch:
            tangents=np.gradient(path,axis=0)
            tangents/=np.linalg.norm(tangents,axis=1)[:,None]
            front=np.array([0.,0.,1.])-tangents*tangents[:,2,None]
            front/=np.maximum(.001,np.linalg.norm(front,axis=1)[:,None])
            seam=path+front*(depth*envelope+.035)[:,None]
            for j in (3,5,7,9,11,13,15,17,19):
                k,q=seam[j:j+2]
                self.tube('hair topstitch',stitch,bone,[k,.25*k+.75*q],.052,.044,6)
        return path

    def patch(self,label,tile,bone,poly,z,thick=.32):
        # Bevelled, padded felt cut-out. Ear clipping keeps the lightning and crescent concave.
        poly=np.asarray(poly,float);center=poly.mean(0)
        sign=np.sum(poly[:,0]*np.roll(poly[:,1],-1)-np.roll(poly[:,0],-1)*poly[:,1])
        if sign<0:poly=poly[::-1]
        low=poly.min(0);span=np.maximum(.01,np.ptp(poly,axis=0));first=len(self.tri);st=len(self.p)
        for scale,zz in ((.93,z-thick),(1.,z),(.94,z+thick)):
            for p in center+(poly-center)*scale:
                self.p.append(np.array([*p,zz])*SCALE+[OFFSETS[self.num],0,0])
                self.uv.append(uv(tile,*((p-low)/span*[1,-1]+[0,1])))
                self.bones.append(part_bone(self.num,bone))
        N=len(poly)
        for j in range(2):
            for i in range(N):
                k=(i+1)%N;a=st+j*N
                self.tri.extend(((a+i,a+k,a+N+k),(a+i,a+N+k,a+N+i)))
        cross=lambda p,q:p[0]*q[1]-p[1]*q[0]
        idx=list(range(N))
        while len(idx)>2:
            for j,b in enumerate(idx):
                a=idx[j-1];c=idx[(j+1)%len(idx)]
                A,B,C=poly[[a,b,c]]
                if cross(B-A,C-B)<=1e-8:continue
                if any(all(cross(n-m,poly[k]-m)>-1e-7 for m,n in ((A,B),(B,C),(C,A))) for k in idx if k not in (a,b,c)):continue
                self.tri.extend(((st+a,st+c,st+b),(st+2*N+a,st+2*N+b,st+2*N+c)))
                idx.pop(j);break
            else:raise ValueError(label+' outline')
        self.face_tiles.extend([tile]*(len(self.tri)-first))
        self.parts.append((self.num,label,first,len(self.tri),st,len(self.p)))

    def jewel(self,x,y,z,r,tile,bone='main'):
        outline=[(x+math.sin(i*math.pi/4)*r*(.34 if i%2 else .74),y+math.cos(i*math.pi/4)*r*(.34 if i%2 else 1)) for i in range(8)]
        self.patch('star setting','gold',bone,outline,z,.13)
        self.patch('four-point satin inset',tile,bone,[(x+.80*(xx-x),y+.80*(yy-y)) for xx,yy in outline],z+.24,.11)

    def arches(self,label,bone,tile,nu,profile):
        a=np.linspace(-math.pi,math.pi,nu+1)
        rows=[]
        for t in np.linspace(0,1,5):
            ring=[]
            for q in a:
                rx,y,rz=profile(t,q)
                ring.append((rx*math.sin(q),y,rz*math.cos(q)))
            rows.append(ring)
        self.grid(label,tile,bone,rows)
        return np.asarray(rows[0])

def sew(m,label,bone,color,path,width=.13,dashed=False):
    pts=np.array(path)
    if dashed:
        for a,b in zip(pts[:-1],pts[1:]):
            m.tube(label,color,bone,[a*.89+b*.11,a*.36+b*.64],width,sides=5)
    else:m.tube(label,color,bone,pts,width,sides=5)

def dress(m,n):
    primary='azure' if n==22 else 'rose'
    lining='blue_mid' if n==22 else 'rose'
    m.ell('stuffed tunic','navy','main',(0,14.7,0),(5.25,6.3,3.5))
    def skirt(t,a):
        w=(1-t)*(6.45+.46*math.cos(10*a))+t*3.35
        return (w,8.2+.46*math.cos(10*a)*(1-t)+t*7.2,w*.70)
    hem=m.arches('scalloped linen skirt','main','navy',50,skirt)
    sew(m,'metallic hem braid','main','gold',hem+[0,.10,0],.15)
    for a in np.linspace(-math.pi,math.pi,13,endpoint=False):
        m.ell('quilted underskirt','cream','main',(5.82*math.sin(a),8.1,4.02*math.cos(a)),(1.48,.95,1.06),nu=8,nv=5)
    # The cape has a short collar at the front center and long asymmetric petals at the sides.
    def cape(t,a):
        openfront=np.exp(-((a-.12)/.40)**2)
        y=10.5+6.50*openfront+.68*math.sin(a)+.15*math.cos(6*a)
        return ((8.21-.9*openfront)*(1-t)+3.35*t,y*(1-t)+20.0*t,(5.70+.55*max(math.cos(a),0))*(1-t)+3.61*t)
    hem=m.arches('ivory split cape','main','ivory',64,cape)
    sew(m,'coloured cape lining','main',lining,hem,.32)
    sew(m,'light cape welt','main','cream',hem+[0,.015,.28],.14)
    sew(m,'cape blanket stitches','main','cream',hem+[0,.03,.24],.115,True)
    def collar(t,a):
        lobe=math.sin(a)**2
        return ((5.10+1.46*lobe)*(1-t)+2.83*t,(17.94-1.88*lobe)*(1-t)+20.55*t,
                (5.63+.30*lobe)*(1-t)+3.45*t)
    fold=m.arches('contrasting sailor collar','main',lining,64,collar)
    sew(m,'gold cord at collar edge','main','gold',fold,.20)
    sew(m,'collar topstitch','main','ivory',fold+[0,.36,.055],.11,True)
    for s in [-1,1]:
        paths=np.array([[s*.48,18.6,3.4],[s*1.05,16.5,4.75],[s*1.3,15.4,4.85],[s*2.3,13.2,5.1]])
        m.tube('ribbon ends',primary,'main',paths,[.35,.66,.60,.1],[.16]*4,8)
    m.jewel(0,18.16,6.02,2.22,'pin_blue' if n==22 else 'pin_rose')
    m.jewel(.25,9.84,4.52,1.08,primary)
    # A raised satin placket and paired thread lines read clearly at game scale.
    placket=[(0,17.10,5.39),(0,16.12,5.35),(0,15.05,5.10),(0,14.10,4.82)]
    m.tube('embroidered bodice placket',lining,'main',placket,[.31,.29,.23,.12],[.13]*4,10)
    for side in (-1,1):
        sew(m,'placket running stitch','main','cream',
            [(side*.21,17.0,5.43),(side*.21,16.05,5.39),(side*.18,15.06,5.15)],.075,True)
        m.tube('short satin pin tail',primary,'main',
               [(side*.42,17.12,6.02),(side*.57,16.45,5.98),(side*.78,15.82,5.86)],
               [.17,.19,.055],[.065,.065,.03],8)
    # Map the approved embroidered letters onto a gently curved cape patch.
    s=-1 if n==22 else 1
    rows=[]
    for t in np.linspace(0,1,4):
        row=[]
        for u in np.linspace(0,1,10):
            a=s*.72+(u-.5)*.65
            rx,y,rz=cape(.14+.22*t,a)
            row.append(((rx+.085)*math.sin(a),y,(rz+.085)*math.cos(a)))
        rows.append(row)
    m.grid('embroidery BLG','badge','main',rows)
    for sign in (-1,1):
        side='L' if sign<0 else 'R'
        hip=side+'_Doll_Hip';knee=side+'_Doll_Knee'
        m.ell('sock','skin',hip,(sign*2.65,6.50,-.10),(1.65,2.6,1.60))
        m.ell('soft boot','navy',knee,(sign*3.10,3.02,.58),(2.28,2.35,2.45))
        m.ell('padded sole','sole',knee,(sign*3.1,1.25,.70),(2.23,.6,2.36),nu=14,nv=6)
        m.jewel(sign*3.14,3.40,2.89,.83,primary,knee)
        tt=np.linspace(-1.50,1.50,13)
        sew(m,'boot stitches',knee,'ice_lit',[(sign*3.1+2.15*math.sin(a),1.58, .7+2.27*math.cos(a)) for a in tt],.08,True)
    for s in (-1,1):
        side='L' if s<0 else 'R';sh=side+'_Doll_Shoulder';el=side+'_Doll_Elbow'
        wave=n==22 and s<0
        hand=([s*8.38,19.4,5.25] if wave else [s*6.35,11.8,3.85]) if n==22 else [s*2.48,15.05,6.06]
        elbow=[s*(7.05 if n==22 else 5.16),15.70,2.35]
        m.ell('rounded quilted shoulder puff','cream',sh,(s*4.52,18.62,.62),
              (1.90,1.86,1.73),nu=26,nv=16)
        m.tube('stuffed sleeve','cream',sh,[[s*3.75,19.4,.0],[s*5.4,18.1,.6],elbow],[1.68,1.88,1.52],sides=16)
        m.ell('quilted elbow','ivory',el,elbow,(1.57,1.63,1.56),nu=18,nv=12)
        m.tube('sleeve folds','ivory',el,[elbow,(np.array(elbow)+hand)*.5,hand],[1.56,1.67,1.22],sides=16)
        m.ell('handsewn mitten','skin',el,hand,(1.68,1.99,1.49),s*.24,nu=22,nv=14)
    if n==33:
        m.ell('spool core','rose','main',(0,15.65,6.33),(1.73,1.94,1.35))
        for y in [13.86,17.40]:
            m.ell('spool rim','gold','main',(0,y,6.34),(1.98,.39,1.53))
        t=np.linspace(0,TAU*5,78)
        sew(m,'wound embroidery floss','main','rose_lit',[(1.62*math.sin(a),14.17+2.90*i/(len(t)-1),6.33+1.28*math.cos(a)) for i,a in enumerate(t)],.14)
        sew(m,'loose thread','main','rose',[(.7,14,7.1),(1.0,13.0,6.9),(1.5,12.1,6.3),(1.2,11,5.8)],.14)

def rounded_rect(cx,cy,w,h,r):
    pts=[]
    for dx,dy,theta in [(w/2-r,h/2-r,0),(-w/2+r,h/2-r,90),(-w/2+r,-h/2+r,180),(w/2-r,-h/2+r,270)]:
        for t in np.linspace(theta,theta+90,5)*math.pi/180:pts.append((cx+dx+r*math.cos(t),cy+dy+r*math.sin(t)))
    return pts

def head(m,n):
    b='Doll_Head';blue=n==22
    dark='blue' if blue else 'ice_shadow';mid='blue_mid' if blue else 'ice';light='blue_lit' if blue else 'ice_lit'
    m.ell('embroidered face','face'+str(n),b,(0,26.8,0),(8.05,7.50,6.8),nu=32,nv=19)
    # A single closed scalp with a real hairline: full nape, open face.
    rows=[]
    for v in np.linspace(0,1,12):
        ring=[]
        for a in np.linspace(-math.pi,math.pi,35):
            low=-.76+1.07*(max(0,math.cos(a))**2)
            phi=low+(math.pi/2-low)*v
            ring.append((8.58*math.sin(a)*math.cos(phi),27.45+8.33*math.sin(phi),-.46+7.08*math.cos(a)*math.cos(phi)))
        rows.append(ring)
    m.grid('felt wig cap',mid,b,rows)
    for i,a in enumerate(np.linspace(.86,TAU-.86,11)):
        s,c=math.sin(a),math.cos(a)
        end=15.0+2.40*math.cos(3*a) if blue else 23.0+.85*math.cos(3*a)
        sweep=(.88 if i%2 else -.68) if blue else 0.
        controls=[[5.5*s,33.4,4.95*c-.5],[9.0*s,29.2,7.0*c-.5],[(7.45*s)+sweep,end-1.6,5.9*c-1],
                  [(11.0 if blue else 8.85)*s+sweep,end+.5,6.03*c-1]]
        path=m.lock('layered long hair' if blue else 'bob panel',[dark,mid,light,mid][i%4],b,
                    controls,2.57 if blue else 2.14,1.16,light if i%2==0 else None)
        # A low raised satin filament gives each broad felt lock a distinct strand flow.
        radial=np.array([s,0.,c]);radial/=max(1e-8,np.linalg.norm(radial))
        strand='blue_lit' if blue else ('rose_lit' if i%4==0 else 'ice_lit')
        m.tube('raised hair strand channel',strand,b,path+radial*.58,.125,.048,8)
    for i,(x0,x1,x2,yy,ww) in enumerate([(-2,-3.8,-7.35,27.65,2.13),(-2.2,.3,2.55,28.32,2.42),
                                        (-.8,4.15,7.5,30.0,1.92),(3.2,6.9,8.26,26.7,1.48)]):
        if n==33 and i==1: x2,yy=1.0,27.1
        controls=[[x0,35.13,2],[x1-.45,34.5,4.95],[x1,yy+1.4,6.95],[x2,yy,6.6-.032*x2*x2]]
        path=m.lock('swept fringe',[mid,mid,light,mid][i],b,controls,ww,1.11,light)
        radial=np.array([x2*.18,0.,1.]);radial/=np.linalg.norm(radial)
        m.tube('fringe satin filament','ice_lit' if not blue else 'blue_lit',b,
               path+radial*.47,.105,.042,7)
    for s in (-1,1):
        m.lock('cheek lock',mid,b,[[s*5.4,33,2.6],[s*8.3,31.1,3.72],[s*8.8,25.1,3.9],
                                   [s*(8.6 if blue else 7.4),23.5,4.25]],1.6,1.03,light)
    if blue:
        for s in (-1,1):
            m.lock('turned shoulder curl',dark,b,[[s*7.5,27.6,1.05],[s*7.55,22.8,3.1],
                   [s*9.34,19.7,3.65],[s*11.35,20.85,2.40]],1.32,.82,light)
        bolt=[(-1.4,34.9),(-2.8,36.9),(-1.4,37.15),(-1.88,38.45),(4.5,41.00),(1.45,37.75),(2.50,37.6),(.05,34.85)]
        m.patch('lightning cowlick',mid,b,bolt,0,.56)
        sew(m,'cowlick topstitch',b,light,[[-1.1,38.46,.56],[.05,38.9,.57],[1.19,39.39,.57],[2.29,39.85,.56]],.075,True)
        x,y=-5.86,32.22
        m.patch('TV binding','ink',b,rounded_rect(x,y,4.17,3.11,.62),4.94,.26)
        m.patch('ivory TV screen','ivory',b,rounded_rect(x,y,3.56,2.49,.48),5.24,.08)
        for s in [-1,1]:
            sew(m,'TV face',b,'ink',[(x+s*.91-.24,y+.03,5.39),(x+s*.91,y+.34,5.4),(x+s*.91+.26,y+.03,5.39)],.09)
            sew(m,'TV aerial',b,'ink',[(x+s*.56,y+1.25,4.99),(x+s*1.05,y+2.05,4.92)],.145)
        sew(m,'TV smile',b,'ink',[(x-.42,y-.36,5.39),(x,y-.60,5.41),(x+.42,y-.36,5.39)],.091)
        for i in range(next(p[4] for p in reversed(m.parts) if p[1]=='TV binding'),len(m.p)):
            m.p[i][2]+=2.15*SCALE
    else:
        cres=[(-.2,35.1),(-1.12,36.2),(-1.68,37.4),(-1.53,38.5),(-.62,39.6),(.5,40.02),
              (.05,39.0),(.07,38.4),(.49,37.62),(1.35,37.16),(2.15,37.0),(1.45,35.3)]
        m.patch('crescent cowlick','ice_lit',b,cres,-.18,.49)
        for i in range(4):
            controls=[[6.82,32.9,.2],[10.0+i*.63,38.1-i*.3,-.33*i],
                      [10.6+i*.5,29.2-i*.35,-.6*i],[10.1+i*.62,25.2+.8*i,-1-.48*i]]
            path=m.lock('high side ponytail',[mid,light,dark,mid][i],b,controls,1.75,1.2,light if i<2 else None)
            m.tube('ponytail satin filament','rose_lit' if i%2 else 'azure',b,
                   path+np.array([.9,0.,.18]),.14,.05,8)
        m.ell('play button hair tie','navy',b,(6.75,32.15,4.52),(1.85,1.69,1.01),nu=20,nv=10)
        m.patch('play triangle','cream',b,[(6.25,31.36),(7.6,32.10),(6.25,32.91)],5.48,.09)
        m.lock('rose hair ribbon','rose',b,[[7.2,31.36,3.40],[7.28,30.1,4.1],[8.25,28.8,4.5],[8.3,28.0,4.45]],.51,.25)
        for i in range(next(p[4] for p in reversed(m.parts) if p[1]=='play button hair tie'),len(m.p)):
            m.p[i][2]+=2.16*SCALE

def build_model():
    m=Model()
    for n in (22,33):
        m.num=n;dress(m,n);head(m,n)
    return m

