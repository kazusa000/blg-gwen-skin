"""Open silver championship cup, spun metal body, pierced handles and crystal engraving."""
import numpy as np
from core import CUP_H,unit
TAU=2*np.pi

def sculpt(mesh,uv,solid):
    def vessel(profile,tile,steps=44,flute=0.):
        pts=[];faces=[];tex=[]
        for k,(r,y) in enumerate(profile):
            for j in range(steps+1):
                u=j/steps;a=u*TAU
                rr=r*(1+flute*np.cos(a*12)*np.sin(np.pi*k/(len(profile)-1)))
                pts.append((rr*np.sin(a),y,rr*np.cos(a)))
                tex.append(uv((0,64*tile,512,64),u,k/(len(profile)-1)))
            if k:
                for j in range(steps):
                    a=(k-1)*(steps+1)+j;b=a+steps+1
                    faces.extend(((a,a+1,b+1),(a,b+1,b)))
        mesh.surf('Cup',pts,faces,tex)
    vessel([(0,1),(32,1),(35,3),(35,5),(32,6),(31,7)],0,32)
    vessel([(31,6),(30,9),(28,14),(26,16)],3,32)
    vessel([(29,13),(29.5,15),(27,17),(22,18),(17,21),(13,24)],1,40)
    vessel([(13,24),(12,26),(10,32),(8,43),(8,50),(10,53),(15,55)],0)
    vessel([(10,26),(12,28),(12,30),(10,31)],5,32)
    vessel([(14,50),(16,52),(16,54),(14,56)],1,36)
    # The lower cup blooms from the neck, then rolls gently in below the lip.
    vessel([(12,54),(17,57),(22,62),(31,68),(37,78),(40,88),(42,102),(42,114),(43,120),(45,123)],0,48,.036)
    vessel([(44,119),(45.5,120),(45.8,122),(45,123)],1,48)
    vessel([(45,122.5),(46.5,123),(46.7,124.5),(46,125),(44.4,125)],4,48)
    vessel([(44.4,125),(42.8,124.8),(42,123.6),(41.3,121)],1,48)
    vessel([(41.3,121),(40,111),(38,98),(34,87),(28,80),(19,75),(8,72),(0,71.5)],2,48)

    def spline(points):
        pts=np.asarray(points,float);pad=np.vstack((pts[0],pts,pts[-1]));res=[]
        for a,b,c,d in zip(pad,pad[1:],pad[2:],pad[3:]):
            for t in np.linspace(0,1,5,endpoint=False):
                res.append(.5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t**3))
        return np.vstack((res,pts[-1]))
    for sign in (-1,1):
        # Two solid forked ears; a full window of negative space separates each from the bowl.
        xy=spline([(38,109),(48,119),(61,135),(75,139),(79,133),(77,122),(69,108),(58,95),(47,83),(36,78)])
        path=np.column_stack((sign*xy[:,0],xy[:,1],-3+3*np.sin(np.linspace(0,np.pi,len(xy)))))
        pct=np.linspace(0,1,len(path));rad=3.4+2.5*np.sin(pct*np.pi)**.8
        axis=np.gradient(path,axis=0);perp=np.asarray([unit([-v[1],v[0],0]) for v in axis])
        cross=[(-1.,0),(-.64,1),(.44,1),(1,.13),(.57,-1),(-.62,-1)]
        p=[];f=[];tex=[]
        for k,(center,r) in enumerate(zip(path,rad)):
            for j,(x,z) in enumerate(cross):
                p.append(center+perp[k]*r*x+[0,0,3.4*z])
                tex.append(uv((0,0,512,64),(.2+j/6)%1,pct[k]))
            if k:
                for j in range(6):
                    a=(k-1)*6+j;b=(k-1)*6+(j+1)%6
                    f.extend(((a,b,b+6),(a,b+6,a+6)))
        mesh.surf('Cup',p,f,tex)
        mesh.tube('Cup',path+perp*(rad*.21)[:,None]+[0,0,3.8],.82,1,5)
    for j in range(10):
        a=TAU*j/10;v=np.linspace(0,1,12);r=np.interp(v,[0,.22,.5,.75,1],[18,26,33,38,40.5])
        y=np.interp(v,[0,.22,.5,.75,1],[57,63,70,80,91]);angle=a+.08*np.sin(np.pi*v)
        mesh.tube('Cup',np.stack((r*np.sin(angle),y,r*np.cos(angle)),axis=1),.78,7,5)
    def gem(x,y,z,r):
        p=np.array([[x,y+r,z],[x+r*.68,y,z],[x,y-r,z],[x-r*.68,y,z],[x,y,z+3]])
        f=[(0,1,4),(1,2,4),(2,3,4),(3,0,4)]
        for face,col in zip(f,(1,2,7,4)):
            mesh.surf('Cup',p[list(face)],[tuple(range(3))],[solid(col)]*3)
    gem(0,95,43,11)
    for sign in (-1,1):gem(sign*75,135,2,4)

