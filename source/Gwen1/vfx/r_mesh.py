"""Particle-local SCB geometry for the crystal needle, eye threads and body orbit."""
import math
import struct
from pathlib import Path

import numpy as np

MESH_ROOT='assets/characters/gwen/skins/base/particles/blg_needlework/'
MESH_DIR=Path(__file__).resolve().parent/'build'/'r-meshes'
EYE_Z=-44.
DRAW_STEPS=(('r_pull_loose',0.,.085),('r_pull_half',.045,.095),('r_pull_taut',.105,.145))


class Surface:
    def __init__(self):
        self.vertices=[]
        self.lookup={}
        self.faces=[]

    def polygon(self,points,uv):
        ids=[]
        for point in points:
            p=tuple(round(float(x),6) for x in point)
            if p not in self.lookup:
                self.lookup[p]=len(self.vertices)
                self.vertices.append(p)
            ids.append(self.lookup[p])
        for j in range(1,len(ids)-1):
            corners=[0,j,j+1]
            tri=[ids[i] for i in corners]
            if len(set(tri))==3:
                a,b,c=(np.array(self.vertices[i]) for i in tri)
                if np.linalg.norm(np.cross(b-a,c-a))>1.e-6:
                    self.faces.append((tri,[uv[i] for i in corners]))

    def enamel(self,points,band,flip=False):
        # U follows the length of every face, including the gold eye rim.
        # Its registration is shared by the moving reflection pass.
        uv=[(.04+.92*(z+76)/210, (band+.50+.23*math.tanh((y+x*.5)/8))/8)
            for x,y,z in points]
        self.polygon(points[::-1] if flip else points,uv[::-1] if flip else uv)

    def encode(self):
        xyz=np.array(self.vertices,dtype='<f4')
        bounds=(*xyz.min(0),*np.ptp(xyz,axis=0))
        header=struct.pack('<8sHH128sIII6fI',b'r3d2Mesh',3,2,b'',len(xyz),len(self.faces),2,*bounds,0)
        triangles=b''.join(struct.pack('<3I64s6f',*ids,b'lambert1',
                          *(u for u,v in uv),*(v for u,v in uv)) for ids,uv in self.faces)
        return header+xyz.tobytes()+bytes(12)+triangles


def make_needle():
    m=Surface()
    # Z, left and right outer radius, diamond-shaped eye opening, ridge depth.
    rows=[(-74,0,0,0,0),(-64,8.5,4.,0,2.1),(-57,13,8.,1.6,3.8),
          (-44,17,13.2,4.65,5.1),(-33,14.6,16,2.8,5.6),(-21,10.2,12,0,5.0),
          (-13,14,11.6,0,5.4),(1,10.6,9.8,0,5.1),(32,8.2,7.4,0,4.1),
          (63,7.0,6.6,0,3.55),(96,4.5,3.8,0,2.7),(132,0,0,0,0)]
    for sign in (-1,1):
        sections=[]
        for z,left,right,hole,h in rows:
            outer=left if sign<0 else right
            span=outer-hole
            # Cross-section has a gold inner bevel, two broad crystal planes and a sharp edge.
            sections.append([(xx,sign*(hole+span*t),z) for xx,t in
                ((.39*h,0),(h,.15 if hole else .01),(.77*h,.52),(.36*h,.85),
                 (0,1),(-.36*h,.85),(-.77*h,.52),(-h,.15 if hole else .01),(-.39*h,0))])
        for j,(a,b) in enumerate(zip(sections,sections[1:])):
            eye=bool(rows[j][3] or rows[j+1][3])
            for k in range(8):
                strip=min(k,7-k)
                if strip==0 and eye: band=5
                elif strip==3: band=6 if sign>0 and j>=5 else 4
                elif sign<0: band=0 if strip<2 else 1
                else: band=2 if strip<2 else 3
                quad=[a[k],a[k+1],b[k+1],b[k]]
                if strip in (1,2) and j in (5,7,9) and (strip+j//2)%2:
                    alternate=1-band if sign<0 else 5-band
                    if j==7:
                        quad=quad[1:]+quad[:1]
                    m.enamel(quad[:3],band,sign<0)
                    m.enamel([quad[0],quad[2],quad[3]],alternate,sign<0)
                else:
                    m.enamel(quad,band,sign<0)
            if eye:
                m.enamel([a[8],a[0],b[0],b[8]],5,sign<0)
    # Jewel clasp at the weld, visible from either broad side. A thin metal
    # setting surrounds an eight-facet, four-point stone.
    for face in (-1,1):
        rim=[]; gem=[]
        for i in range(8):
            t=math.pi*i/4
            radius=1 if i%2==0 else .36
            y,z=9.9*radius*math.cos(t),16*radius*math.sin(t)
            rim.append((face*5.8,y,z-12))
            gem.append((face*6.65,.78*y,.78*z-12))
        for i in range(8):
            j=(i+1)%8
            m.enamel([(face*3.65,*rim[i][1:]),(face*3.65,*rim[j][1:]),rim[j],rim[i]],6,face<0)
            m.enamel([rim[i],rim[j],gem[j],gem[i]],5 if i%3 else 6,face<0)
            m.enamel([gem[i],gem[j],(face*9.2,0,-12)],(4,0,1,0,2,3,0,4)[i],face<0)
    return m


def make_silk(bend,parity=1,reach=74):
    m=Surface()
    centers=[]
    radii=[]
    # The short end curls behind the eye, and the long end emerges on its front face.
    for t in np.linspace(1,0,13)[:-1]:
        centers.append(np.array((10*t,-parity*10*t**1.65,EYE_Z+11*t**1.35)))
        radii.append(.12+.98*(1-t**2))
    for t in np.linspace(0,1,51):
        droop=math.sin(math.pi*t)
        front=-6.5*math.sin(min(1,t/.20)*math.pi*.5)
        centers.append(np.array((front+5.8*math.sin(2.2*math.pi*t)*droop*bend,
              parity*bend*(-26*math.sin(1.2*math.pi*t)+9.3*math.sin(2.8*math.pi*t)),
              EYE_Z-reach*t+7*bend*math.sin(2*math.pi*t))))
        radii.append((1.10+.65*droop)*(1-.96*t**3))
    rings=[]
    sides=6
    for i,(center,rad) in enumerate(zip(centers,radii)):
        tangent=centers[min(i+1,len(centers)-1)]-centers[max(0,i-1)]
        tangent/=np.linalg.norm(tangent)
        normal=np.cross(tangent,[0,1,0])
        normal/=np.linalg.norm(normal)
        across=np.cross(tangent,normal)
        rings.append([center+rad*(normal*math.cos(k*math.tau/sides)+across*math.sin(k*math.tau/sides))
                      for k in range(sides)])
    for j,(a,b) in enumerate(zip(rings,rings[1:])):
        for k in range(sides):
            h=(k+1)%sides; u=j/(len(rings)-1); u2=(j+1)/(len(rings)-1)
            m.polygon([a[k],a[h],b[h],b[k]],[(u,k/sides),(u,(k+1)/sides),(u2,(k+1)/sides),(u2,k/sides)])
    return m


def needle_veil():
    m=Surface()
    # Two open sheets wind around the eye. Their converging ends leave the tip clear.
    for lobe in range(2):
        rows=[]
        for u in np.linspace(0,1,48):
            envelope=math.sin(math.pi*u)**.72
            twist=.62*math.tau*u+lobe*math.pi+.33*math.sin(2*math.pi*u+lobe)
            radius=1.2+envelope*(24+4*math.sin(8*u+lobe))
            arc=(.78+.39*math.sin(math.pi*u))*envelope
            z=-129+193*u
            row=[]
            for v in np.linspace(0,1,7):
                theta=twist+(2*v-1)*arc
                row.append((radius*math.cos(theta),radius*math.sin(theta),
                            z+6*(2*v-1)*envelope))
            rows.append(row)
        for i,(a,b) in enumerate(zip(rows,rows[1:])):
            u=i/(len(rows)-1);u2=(i+1)/(len(rows)-1)
            for j in range(6):
                v=j/6;v2=(j+1)/6
                m.polygon([a[j],b[j],b[j+1],a[j+1]],[(u,v),(u2,v),(u2,v2),(u,v2)])
    return m


def flight_wake():
    """Two intersecting veils share a spine and U coordinate from the needle eye to the tip."""
    surface = Surface()
    for plane in (0., math.pi / 2):
        previous = None
        for row in range(41):
            u = row / 40
            belly = math.sin(math.pi * u)
            center = np.array((2.8 * belly, 6.2 * math.sin(1.6 * math.pi * u) * belly,
                               EYE_Z + 16 - 420 * u))
            half_width = .85 + 36 * (1 - math.exp(-10 * u)) * (1 - u) ** .68
            angle = plane + .17 * math.sin(math.pi * u - .27)
            across = np.array((math.cos(angle), math.sin(angle), 0))
            line = [center + side * across * half_width for side in (-1, 0, 1)]
            if previous is not None:
                for col in range(2):
                    v = col / 2
                    surface.polygon([previous[col], line[col], line[col+1], previous[col+1]],
                                    [((row-1)/40, v), (u, v), (u, v+.5), ((row-1)/40, v+.5)])
            previous = line
    return surface


def projectile():
    # The front of the wake shares the needle's draw. It stays attached even
    # when the renderer drops the optional mesh or limits the trail particle count.
    combined = Surface()
    for tail, mesh in ((False,make_needle()),(True,flight_wake())):
        for ids, uv in mesh.faces:
            points = [mesh.vertices[i] for i in ids]
            if tail:
                points = [(x*.98,y*.98,-37+(z+28)*.43) for x,y,z in points]
            else:
                # Double the solid crystal itself, in both transverse axes.
                points = [(2*x,2*y,z) for x,y,z in points]
            uv = [(u,(.508 if tail else .004) + v*.488) for u,v in uv]
            combined.polygon(points,uv)
    return combined


def tip_glint():
    surface = Surface()
    # Two crossed planes keep the four-point reflection readable as the needle turns.
    for angle in (.42, .42 + math.pi/2):
        points = [(side*19*math.cos(angle), side*19*math.sin(angle), 117 + longitudinal*25)
                  for side,longitudinal in ((-1,-1),(1,-1),(1,1),(-1,1))]
        surface.polygon(points, [(0,1),(1,1),(1,0),(0,0)])
    return surface


def make_orbit(vapour=False):
    m=Surface()
    edges=[]
    for t in np.linspace(0,1,53):
        theta=math.radians(-210+237*t) if vapour else math.radians(-182+206*t)
        radius=65+14*math.sin(math.pi*t)+5*t
        y=-39+74*t+10*math.sin(theta+.2)
        w=1+12.8*math.sin(math.pi*t)**.8
        if vapour:
            radius+=3+2.8*math.sin(7*t)
            y-=4+4*math.cos(5*t)
            w=.4+(34+4*math.sin(5*t))*math.sin(math.pi*t)**.8
        radial=np.array((math.cos(theta),0,math.sin(theta)))
        center=radial*radius+np.array((0,y,0))
        bank=.65*math.sin(1.5*theta)
        across=radial*math.sin(bank)+np.array((0,math.cos(bank),0))
        edges.append([center-w*across,center+w*across])
    for j,(a,b) in enumerate(zip(edges,edges[1:])):
        u=j/(len(edges)-1);u2=(j+1)/(len(edges)-1)
        m.polygon([a[0],a[1],b[1],b[0]],[(u,0),(u,1),(u2,1),(u2,0)])
    return m


def orbit_grains():
    m=Surface()
    rng=np.random.default_rng(1097)
    for t in np.linspace(.1,.92,27):
        theta=math.radians(-211+225*t+rng.uniform(-4,4))
        radial=np.array((math.cos(theta),0,math.sin(theta)))
        across=np.array((-math.sin(theta),0,math.cos(theta)))+.34*radial
        up=np.array((0,1,0))
        center=radial*(70+12*math.sin(math.pi*t)+rng.uniform(-6,11))
        center+=up*(-39+74*t+10*math.sin(theta+.2)+rng.uniform(-22,21))
        dx=across*rng.uniform(1.5,4.1)
        dy=up*rng.uniform(1.8,4.4)
        m.polygon([center-dx-dy,center+dx-dy,center+dx+dy,center-dx+dy],
                  [(0,0),(1,0),(1,1),(0,1)])
    return m


def build():
    designs={'r_crystal_needle':make_needle(),'r_spiral':make_orbit(),'r_flight_wake':flight_wake(),
             'r_projectile':projectile(),'r_tip_glint':tip_glint(),
             'r_needle_veil':needle_veil(),'r_orbit_veil':make_orbit(vapour=True),'r_orbit_grains':orbit_grains(),
             'r_slack_ice':make_silk(.93,-1,68),'r_slack_rose':make_silk(1.28,1,76),
             'r_slack_crown':make_silk(1.07,-1,90),
             'r_pull_loose':make_silk(1,1,77),'r_pull_half':make_silk(.57,1,101),
             'r_pull_taut':make_silk(.075,1,135)}
    MESH_DIR.mkdir(exist_ok=True,parents=True)
    for name,design in designs.items():
        (MESH_DIR/(name+'.scb')).write_bytes(design.encode())
    return set(designs)
