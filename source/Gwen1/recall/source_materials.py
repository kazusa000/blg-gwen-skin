"""Registered roughness, metallic and ambient occlusion maps for the native shaders."""
import json
import numpy as np
from PIL import Image,ImageDraw
from source_layout import OUT,TILES,ATLAS,WEAPON_SIZE,VIEWS
from repair_paint import encode_particle,decode_full
PROFILES={
 'satin':(.49,.015,.96),'cloth':(.72,0,.97),'pile':(.89,0,.98),'skin':(.64,0,.97),
 'hair':(.36,.015,.97),'gold':(.285,.86,.96),'silver':(.21,.94,.97),'steel':(.34,.84,.92),
 'crystal':(.155,.025,.98),'enamel':(.285,.035,.98),'screen':(.19,.015,.99),'ink':(.47,.015,.96),
 'leather':(.49,.005,.96),'stitch':(.50,.22,.95),'plush':(.87,0,.98)}
def category(name):
    n=name.lower()
    for words,target in [
        (('ermine','fleece'),'pile'),(('stocking',),'cloth'),(('matte','porcelain','skin','mucosa','tongue','teeth'),'skin'),
        (('crystal','gemstone'),'crystal'),(('enamel',),'enamel'),(('silver','filigree'),'silver'),
        (('champagne embroidery',),'stitch'),(('gold','champagne'),'gold'),(('shoe','gauntlet'),'leather'),
        (('fibres','locks','pearl ·','strand','nape','fringe'),'hair'),(('silk','bodice','satin','brocade','organza','drawing'),'satin')]:
        if any(w in n for w in words):return target
    return 'cloth'
def tint(key):return tuple(round(255*n) for n in PROFILES[key])
def halfbox(key):
    x,y,w,h=TILES[key];return x//2,y//2,w//2,h//2
def tile(im,key,profile,method):
    x,y,w,h=halfbox(key);rough,metal,ao=PROFILES[profile]
    v,u=np.mgrid[:h,:w]/np.array([max(1,h-1),max(1,w-1)])[:,None,None]
    if method=='thread':variation=.019*np.cos(u*282)+.013*np.cos(v*187+.20*np.sin(u*23))
    elif method=='silk':variation=.031*np.cos(2*np.pi*(v*14+u*.5))+.012*np.cos(u*420)
    elif method=='polish':variation=.043*np.cos(2*np.pi*(v*7+.22*u))+.014*np.cos(2*np.pi*(105*v+u))
    else:variation=.015*np.cos(2*np.pi*(u*2+v))
    a=np.stack([rough+variation,np.full_like(v,metal),ao-.035*(variation<-.025)],axis=-1)
    if key=='wall/steel':
        from hinge_finish import inlay
        lip,cut,enamel,rivet,bezel=inlay(u,v)
        for mask,values in [(lip,PROFILES['gold']),(enamel,PROFILES['enamel']),(rivet,(.44,.72,.82)),(bezel,PROFILES['gold'])]:
            a=a*(1-mask[:,:,None])+np.array(values)*mask[:,:,None]
    arr=np.uint8(np.clip(a,0,1)*255);im.paste(Image.fromarray(np.pad(arr,((2,2),(2,2),(0,0)),'edge')),(x-2,y-2))
def write(name,im):
    im=im.convert('RGBA');raw=encode_particle(im)
    assert np.array_equal(np.asarray(decode_full(raw)),np.asarray(im))
    (OUT/(name+'.tex')).write_bytes(raw)
def author():
    desc=json.loads((OUT/'source.json').read_text('utf8'))
    body=Image.new('RGB',tuple(a//2 for a in ATLAS),tint('satin'));pen=ImageDraw.Draw(body)
    for r in desc['parts']:
        if r['role']!='Body' or r['kind']!='mesh':continue
        with np.load(OUT/'parts'/r['file']) as d:v,f=d['v'],d['f']
        mi=np.load((OUT/'parts'/r['file']).with_name(r['file'].replace('.npz','-materials.npy')))
        for j,name in enumerate(r['materials']):
            profile=category(name)
            if profile=='satin':continue
            tri=np.rint(v['uv'][f[mi==j]]*body.size).astype('i')
            if not len(tri):continue
            for q in tri:
                pen.polygon(tuple(map(tuple,q)),fill=tint(profile))
    for s in desc['swatches']:
        idx=desc['swatches'][s]['idx'];x=(4180+idx%6*64)//2;y=(40+idx//6*64)//2
        pen.rectangle((x-14,y-14,x+14,y+14), fill=tint(category(s)))
    for k in VIEWS:
        tile(body,'pile/'+k,'pile','thread')
        # Source face views also include the lifted fringe. Identify the actual
        # registered hair from its cool/pearl colour relative to the skin paint.
        im=Image.open(OUT/'face'/(k+'.png')).convert('RGB').resize((500,500),Image.Resampling.LANCZOS)
        rgb=np.asarray(im,dtype='f');hair=np.clip((rgb[:,:,2]-rgb[:,:,0]+37)/38,0,1)
        a=np.zeros((500,500,3),'B');a[:,:,0]=(PROFILES['skin'][0]-.22*hair)*255;a[:,:,2]=248
        x,y,*_=halfbox('face/'+k);body.paste(Image.fromarray(np.pad(a,((2,2),(2,2),(0,0)),'edge')),(x-2,y-2))
    for i in range(8):tile(body,'dye/'+str(i),'hair','silk')
    tile(body,'gwen-hair-streaks.png','hair','silk')
    from train_silk import atlas as train_atlas, IMAGE
    x,y,w,h=halfbox(IMAGE)
    response=train_atlas()[1].resize((w,h),Image.Resampling.LANCZOS)
    body.paste(Image.fromarray(np.pad(np.asarray(response),((2,2),(2,2),(0,0)),'edge')),(x-2,y-2))
    tile(body,'bodice','satin','thread')
    # Couching and embroidery on the silk placket have their own response.
    from source_paint import corset
    x,y,w,h=halfbox('bodice');photo=np.asarray(corset(w,h),dtype='f')/255
    warm=np.clip((photo[:,:,0]-photo[:,:,2]-.012)*9,0,1)*np.clip((.83-photo.mean(2))*5,0,1)
    sub=np.array(body.crop((x,y,x+w,y+h)));sub[:,:,0]=np.clip(sub[:,:,0]-warm*13,0,255);sub[:,:,1]=np.uint8(4+warm*76)
    body.paste(Image.fromarray(sub),(x,y));write('surface-rma',body)
    weapon=Image.new('RGB',tuple(a//2 for a in WEAPON_SIZE),tint('steel'))
    for key,material,style in [('gold','gold','polish'),('steel','steel','polish'),('blue','crystal','polish'),('pink','crystal','polish'),('ink','ink','none')]:
        tile(weapon,'wall/'+key,material,style)
    for key,material in [('Prismatic glass inlay','crystal'),('Polished champagne relief','gold'),('Pearl and cloisonné enamel','enamel'),('Ivory television glass','screen')]:
        tile(weapon,'weapon/'+key,material,'polish' if material=='gold' else 'none')
    write('weapon-rma',weapon)
if __name__=='__main__':author()

