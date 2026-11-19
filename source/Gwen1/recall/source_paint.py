"""Native diffuse from registered source art, both corset UVs and individual fibre dyes."""
import json
import numpy as np
from PIL import Image,ImageDraw
from source_layout import OUT,TILES,ATLAS,VIEWS,WEAPON_SIZE,WEAPON_CROPS
from ponytail_color import DYES,rgb
from repair_paint import decode_full
from diffuse_tex import encode
def image(a):return Image.fromarray(np.uint8(np.clip(a,0,255)))
def sample(im,uv):
    a=im;h,w=a.shape[:2];q=uv.clip(0,1)*[w-1,h-1]
    x,y=q.astype(int).T;dx,dy=(q-q.astype(int)).T
    x1=np.minimum(x+1,w-1);y1=np.minimum(y+1,h-1);dx=dx[:,None];dy=dy[:,None]
    return (1-dy)*((1-dx)*a[y,x]+dx*a[y,x1])+dy*((1-dx)*a[y1,x]+dx*a[y1,x1])
def grade(a,contrast=1.12):
    a=np.asarray(a,dtype='f');l=a@[.2126,.7152,.0722]
    # Leave saturated dye legible. Roll off near-white studio values before game lighting.
    stops=[0,47,95,148,185,220,245,255]
    value=np.interp(l,stops,[0,36,82,141,185,222,245,251])
    return image((l+(value-l)*contrast)[...,None]+1.065*(a-l[...,None]))
def corset(w,h):
    with np.load(OUT/'corset-layers.npz') as source_data:d=dict(source_data)
    uv=d['surface']*[w,h]
    source=np.asarray(Image.open(OUT/'source-images/gwen-corset.png').convert('RGB'))
    front=np.asarray(Image.open(OUT/'source-images/turnaround-v1.png').convert('RGB'))
    im=np.zeros((h,w,3),'f');filled=np.zeros((h,w),bool)
    for i,(a,b,c) in enumerate(uv):
        lo=np.maximum(0,np.floor(np.minimum.reduce([a,b,c])).astype(int));hi=np.minimum([w,h],1+np.ceil(np.maximum.reduce([a,b,c])).astype(int))
        x0,y0=lo;x1,y1=hi
        if x0>=x1 or y0>=y1:continue
        y,x=np.mgrid[y0:y1,x0:x1];delta=b-a;edge=c-a;det=delta[0]*edge[1]-delta[1]*edge[0]
        if abs(det)<1e-9:continue
        xx=x+.5-a[0];yy=y+.5-a[1];l=(xx*edge[1]-yy*edge[0])/det;m=(delta[0]*yy-delta[1]*xx)/det
        ok=(l>=-1e-6)&(m>=-1e-6)&(l+m<=1.000001)
        if not ok.any():continue
        ba=np.stack([1-l[ok]-m[ok],l[ok],m[ok]],axis=1)
        lower=sample(source,ba@d['under'][i]);upper=sample(front,ba@d['over'][i]);ratio=(ba@d['mix'][i])[:,None]
        im[y[ok],x[ok]]=lower*(1-ratio)+upper*ratio;filled[y[ok],x[ok]]=True
    assert filled.mean()>.999,'corset unwrap coverage'
    # Silken piping and couched silver stitches follow the paired upper panel seams.
    yy,xx=np.mgrid[:h,:w];t=(yy+.5)/h;s=np.minimum(xx+.5,w-xx-.5)/w
    curve=.033+.075*np.sin(np.pi*np.clip((t-.06)/.8,0,1))+.033*t
    dist=(s-curve)*w;end=np.clip((t-.08)*22,0,1)*np.clip((.84-t)*18,0,1)
    def line(offset,width):return np.exp(-((dist-offset)/width)**2)*end
    im+=(-12*line(0,3.8)+18*line(-1.4,1.5)+10*line(3.2,.95)*(.48+.52*np.cos(2*np.pi*t*42)))[...,None]*[1,.88,.86]
    from corset_stitch import stitch
    return grade(stitch(im))
def crystal_edges(im,parts,box):
    """Paint a narrow bevel on genuine breaks between the native blade planes."""
    draw=ImageDraw.Draw(im,'RGBA')
    for part in parts:
        if 'ground crystal blade' not in part['name']:continue
        path=OUT/'parts'/part['file']
        with np.load(path) as mesh:
            verts=mesh['v'];faces=mesh['f'][np.load(path.with_name(path.stem+'-materials.npy'))==0]
        positions=verts['p'][faces]
        normals=np.cross(positions[:,1]-positions[:,0],positions[:,2]-positions[:,0])
        normals/=np.maximum(1e-12,np.linalg.norm(normals,axis=1))[:,None]
        texels=verts['uv'][faces]*WEAPON_SIZE-np.array(box[:2])-.5
        shared={}
        for points,normal,triangle in zip(positions,normals,texels):
            if normal[0]<.3:continue
            for a,b in ((0,1),(1,2),(2,0)):
                edge=tuple(sorted((tuple(points[a]),tuple(points[b]))))
                shared.setdefault(edge,[]).append((normal,triangle[[a,b]]))
        for neighbours in shared.values():
            if len(neighbours)!=2:continue
            (normal,line),(other,_)=neighbours
            bend=1-float(normal@other)
            if bend<.032 or np.linalg.norm(line[0]-line[1])<25:continue
            alpha=round(min(36,8+bend*85))
            draw.line([tuple(q) for q in line+(1,1)],fill=(63,47,101,alpha),width=3)
            draw.line([tuple(q) for q in line],fill=(220,243,255,alpha),width=2)
    return im

def atlas():
    desc=json.loads((OUT/'source.json').read_text('utf8'));sheet=Image.new('RGB',ATLAS,(122,111,125))
    weapon=Image.new('RGB',WEAPON_SIZE,(93,81,98))
    def put(key,im):
        x,y,w,h=TILES[key];im=im.convert('RGB').resize((w,h),Image.Resampling.LANCZOS)
        pad=np.pad(np.asarray(im),((4,4),(4,4),(0,0)),'edge')
        target=weapon if key.startswith(('wall/','weapon/')) else sheet
        target.paste(Image.fromarray(pad),(x-4,y-4))
    for fn in ('turnaround-v1.png','gwen-mantle-silk.png','gwen-train-crest.png'):
        put(fn,grade(Image.open(OUT/'source-images'/fn).convert('RGB')))
    original=Image.open(OUT/'source-images/scissors.png').convert('RGB')
    for key in (k for k in TILES if k.startswith('weapon/')):
        box=TILES[key]
        crop=original.crop(WEAPON_CROPS[key.split('/',1)[1]])
        color=np.asarray(crop,dtype='f')
        if 'Prismatic' in key:
            l=color@np.array([.2126,.7152,.0722])
            color=l[:,:,None]+1.08*(color-l[:,:,None])
            color*=.92
        if 'champagne' in key:color*=np.array([.96,.895,.84])
        art=image(color).resize(box[2:],Image.Resampling.LANCZOS)
        if 'Prismatic' in key:art=crystal_edges(art,desc['parts'],box)
        put(key,art)
    put('bodice',corset(*TILES['bodice'][2:]))
    for family in ('pile','face'):
        for key in VIEWS:
            im=Image.open(OUT/family/(key+'.png')).convert('RGBA');bg=Image.new('RGB',im.size,(179,163,176))
            bg.paste(im,mask=im.getchannel('A'));put(family+'/'+key,grade(bg,.78 if family=='face' else 1.05))
    for s in desc['swatches'].values():
        a=np.array(s['linear']);srgb=np.where(a<=.00313,a*12.92,1.055*a**(1/2.4)-.055)
        x=4180+s['idx']%6*64;y=40+s['idx']//6*64
        sheet.paste(grade(np.tile(srgb*255,(56,56,1))),(x-28,y-28))
    for i,(_,root,tip) in enumerate(DYES):
        _,_,w,h=TILES['dye/'+str(i)];t=np.linspace(0,1,w)[None,:,None];s=np.linspace(0,1,h)[:,None,None]
        c=255*((1-.80*t)*rgb(root)+.80*t*rgb(tip))
        # Silk scatters some of the pearl base into both coloured highlights.
        pearl=np.array([244,226,234]);c=c*(.68 if i>=4 else .94)+pearl*(.32 if i>=4 else .06)
        strand=c*(.76+.24*s)+np.exp(-((s-.76)/.15)**2)*[21,21,23]
        put('dye/'+str(i),image(strand))
    for key,base in {'gold':(178,133,116),'steel':(100,81,112),'blue':(64,130,188),'pink':(183,92,145),'ink':(97,70,111)}.items():
        _,_,w,h=TILES['wall/'+key];v,u=np.mgrid[:h,:w]/np.array([h-1,w-1])[:,None,None]
        phase=abs(v-.5)*2
        bands=.69+.16*np.cos(2*np.pi*(v-.22))+.15*np.cos(2*np.pi*(u*.70+v*.35))
        rim=np.exp(-((phase-.84)/.047)**2)+.48*np.exp(-((phase-.66)/.022)**2)
        grain=np.sin(2*np.pi*(v*26+.24*np.sin(u*6)))*1.6
        color=np.array(base)*bands[:,:,None]+rim[:,:,None]*[60,51,44]+grain[:,:,None]
        if key=='steel':
            from hinge_finish import inlay
            lip,cut,enamel,rivet,bezel=inlay(u,v)
            color=color*(1-.34*cut[:,:,None])
            for mask,tone in [(lip,[196,155,131]),(enamel,[98,132,154]),(rivet,[53,49,66]),(bezel,[184,141,119])]:
                color=color*(1-mask[:,:,None])+np.array(tone)*mask[:,:,None]
        put('wall/'+key,image(color))
    sheet=sheet.convert('RGBA')
    cards=np.array(Image.open(OUT/'source-images/gwen-hair-streaks.png').convert('RGBA'))
    a=cards[:,:,3];cards[:,:,:3]=image(.76*cards[:,:,:3]+.24*np.array([238,221,231]))
    cards[a==0,:3]=0
    x,y,w,h=TILES['gwen-hair-streaks.png'];sheet.paste(Image.fromarray(cards),(x,y))
    for name,im in [('surface',sheet),('weapon',weapon.convert('RGBA'))]:
        raw=encode(im);decoded=decode_full(raw)
        assert np.array_equal(np.asarray(decoded),np.asarray(im))
        (OUT/(name+'.tex')).write_bytes(raw)
if __name__=='__main__':atlas()

