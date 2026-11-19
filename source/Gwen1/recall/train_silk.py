"""Sewing-pattern space shared by the Blender garment, native diffuse and reflection mask."""
import numpy as np

SIZE = (1536, 1024)
IMAGE = 'gwen-mantle-silk.png'
# Separate the two outside panels, rolled bindings and floating linings with mip gutters.
PANELS = {
    ('outer', -1): (8, 8, 556, 1008), ('outer', 1): (580, 8, 556, 1008),
    ('facing', -1): (1152, 8, 80, 1008), ('facing', 1): (1248, 8, 80, 1008),
    ('lining', -1): (1344, 8, 80, 1008), ('lining', 1): (1440, 8, 88, 1008),
}
def pattern_uv(kind, side, t, u):
    x,y,w,h = PANELS[kind,side]
    return ((x+.5+(w-1)*u)/SIZE[0], 1-(y+.5+(h-1)*t)/SIZE[1])

def fields(kind, side):
    _,_,w,h = PANELS[kind,side]
    t,u = np.mgrid[0:h,0:w] / np.array([h-1,w-1])[:,None,None]
    edge = np.minimum(u,1-u)
    def line(d,width):
        return np.exp(-(d/width)**2)
    if kind == 'outer':
        # A shallow scallop follows the actual cut of the hem. The crest has an open field.
        hem = .941-.033*np.cos(2*np.pi*(u-.49))
        braid = np.maximum(line(t-hem,.0027),.72*line(t-hem-.013,.0017))
        braid = np.maximum(braid,.8*line(edge-.028,.0035))
        for center in (.075,.50,.925):
            peak = .887-.033*np.cos(2*np.pi*(center-.49))
            diamond = abs(u-center)/.031+abs(t-peak)/.031
            braid = np.maximum(braid,.83*line(diamond-1,.105))
        inset = np.clip((t-hem-.018)*430,0,1)*np.clip((hem+.048-t)*430,0,1)
        base = np.array([221,216,222])
        ripple=u+.043*np.sin(2.2*t)
        fold = -22*np.exp(-((u-.65-.06*np.sin(t*4))/.15)**2)+8*np.cos(2*np.pi*(u*1.4+.15*t))
        fold += 8*line(ripple-.24,.078)-9*line(ripple-.32,.054)+6*line(ripple-.83,.067)
        shade = fold-12*(1-t)**1.7-5*np.exp(-(edge/.034)**2)
        color = base+shade[...,None]*[1.04,.99,.87]
        accent = [164,198,213] if side<0 else [213,178,192]
        color = color*(1-.68*inset[...,None])+np.array(accent)*(.68*inset[...,None])
    else:
        # The two separate lengths of silk keep a single yarn colour all the way to the tip.
        base = np.array(([114,173,201] if side<0 else [200,142,164]) if kind=='lining'
                        else ([159,194,211] if side<0 else [211,169,184]))
        shade = -16*np.cos(2*np.pi*(u+.055*np.sin(4*t)))+12*np.exp(-((u-.32)/.16)**2)-5*(1-t)
        color = base+shade[...,None]
        braid = .78*line(edge-.078,.012)
    weave = .78*np.sin(2*np.pi*(u*w/5.2+t*h/9))+.67*np.sin(2*np.pi*(u*w/4.7-t*h/9.6))
    color += weave[...,None]
    gold = np.array([173,153,145])+np.cos(2*np.pi*t*76)[...,None]*[11,10,9]
    color = color*(1-braid[...,None])+gold*braid[...,None]
    rough = (.50 if kind=='outer' else .44)-.13*braid+.008*weave
    metal = .009+.32*braid
    return np.uint8(np.clip(color,0,255)),np.uint8(255*np.stack((rough,metal,np.full_like(t,.97)),axis=-1))

def atlas(crest_path=None):
    from PIL import Image
    color=Image.new('RGB',SIZE,(215,211,218));rma=Image.new('RGB',SIZE,(126,2,247))
    for (kind,side),(x,y,w,h) in PANELS.items():
        dye,response=fields(kind,side)
        fabric=Image.fromarray(dye)
        if kind=='outer' and side==1 and crest_path is not None:
            # The old decal included photographic folds in its clear margin. Preserve the
            # coloured embroidery but let the new cloth show through between its letters.
            ref=Image.open(crest_path).convert('RGBA')
            a=np.array(ref,dtype=float);r,g,b=a[:,:,:3].transpose(2,0,1)
            blue=np.clip((np.minimum(b-r,g-r)-7)/37,0,1)
            rose=np.clip((np.minimum(r-g,b-g)-8)/40,0,1)*np.clip((r-b+2)/22,0,1)
            alpha=np.maximum(blue,rose)*a[:,:,3]/255
            pigment=np.zeros_like(a)
            pigment[:,:,:3]=np.where((blue>rose)[:,:,None],[35,153,190],[219,112,158])
            pigment[:,:,3]=alpha*255
            mark=Image.fromarray(pigment.astype('uint8')).resize((round(.323*(w-1)),round(.156*(h-1))),Image.Resampling.LANCZOS)
            fabric.paste(mark,(round(.025*(w-1)),round(.73*(h-1))),mark)
        for target,inside in ((color,fabric),(rma,Image.fromarray(response))):
            pad=np.pad(np.asarray(inside),((7,7),(7,7),(0,0)),'edge')
            target.paste(Image.fromarray(pad),(x-7,y-7))
    return color,rma

if __name__=='__main__':
    from core import SKIN
    textures=SKIN/'textures'
    atlas(textures/'gwen-train-crest.png')[0].save(textures/IMAGE,optimize=True)
