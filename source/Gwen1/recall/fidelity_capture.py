"""Capture colour, depth and surface identity from the untouched approved production scene."""
from pathlib import Path
import hashlib
import sys
import bpy
import numpy as np
import OpenImageIO as oiio
from mathutils import Vector
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from fidelity_cameras import VIEWS,HOLDOUT,axes,WIDTH,HEIGHT,SCALE,CENTER
from core import C,WORK
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
category=next((int(a.split('=')[1]) for a in args if a.startswith('group=')),0)
focus='portrait' in args
folder='validation' if any(k in args for k in HOLDOUT) else 'captures' if not category else f'captures-{category}'
pile='pile-hd' in args
face='face-hd' in args
out=WORK/'full-source'/('pile' if pile else 'face') if pile or face else WORK/'groom-1.3'/(folder+('-portrait' if focus else ''));out.mkdir(exist_ok=True,parents=True)
if focus:CENTER=np.array([-4.,149.,0.]);SCALE=111.
if pile:
    WIDTH=HEIGHT=1504;CENTER=np.array([-10.,139.,2.]);SCALE=86.
if face:
    WIDTH=HEIGHT=1000;CENTER=np.array([-5.,166.,5.]);SCALE=49.
s=bpy.context.scene;s.frame_set(1)
kept=set()
for c in s.collection.children:
    if c.name.startswith(('07','09','10')) or 'shears' in c.name.lower() or '2233' in c.name:
        c.hide_render=True
    if c.name[:2] in ('01','02','03','04','05','06','11'):
        for o in c.objects:
            if o.type in ('MESH','CURVES') and not o.hide_render:
                kept.add(o.name)
                o.pass_index=int(c.name[:2])
                if o.type=='CURVES':
                    o.pass_index=16 if 'ringlet fibres' in o.name else 15 if 'swept nape' in o.name else 14
                if category and o.pass_index not in {category,category+10 if category in (4,5) else category}:kept.discard(o.name)
for o in list(s.objects):
    if o.type in ('MESH','CURVE','CURVES','SURFACE','FONT') and o.name not in kept:
        if o.animation_data:o.animation_data_clear()
        o.hide_render=True
print('Visible production assets',len(kept),flush=True)
s.camera=bpy.data.objects.new('Export verification camera',bpy.data.cameras.new('Native orthographic'))
s.collection.objects.link(s.camera)
s.camera.data.type='ORTHO';s.camera.data.ortho_scale=.02*SCALE
s.render.resolution_x=WIDTH;s.render.resolution_y=HEIGHT;s.render.resolution_percentage=100
s.render.film_transparent=True;s.render.use_compositing=False;s.render.use_sequencer=False
s.cycles.samples=10;s.cycles.use_denoising=True;s.cycles.seed=13
if pile or face:s.cycles.samples=32
s.cycles.use_adaptive_sampling=True;s.cycles.adaptive_threshold=.13
s.render.engine='CYCLES'
# A CPU fallback is available when the workstation has no supported compute device.
prefs=bpy.context.preferences.addons['cycles'].preferences
for backend in ('OPTIX','CUDA','HIP','ONEAPI'):
    try:
        prefs.compute_device_type=backend;prefs.refresh_devices()
        gpu=[d for d in prefs.devices if d.type==backend]
        if gpu:
            for d in prefs.devices:d.use=d in gpu
            s.cycles.device='GPU';print('Capture device',backend,[d.name for d in gpu],flush=True);break
    except (TypeError,RuntimeError):pass
layer=bpy.context.view_layer
layer.use_pass_position=True;layer.use_pass_normal=True
layer.use_pass_object_index=True;layer.use_pass_diffuse_color=True
s.render.image_settings.media_type='MULTI_LAYER_IMAGE'
s.render.image_settings.file_format='OPEN_EXR_MULTILAYER'
s.render.image_settings.color_depth='32';s.render.image_settings.exr_codec='ZIP'
keys=[a for a in args if not a.startswith('group=') and a not in ('portrait','pile-hd','face-hd')] or list(VIEWS)
signature=hashlib.sha256(Path(bpy.data.filepath).read_bytes()+Path(__file__).read_bytes()+(HERE/'fidelity_cameras.py').read_bytes()).hexdigest()
for key in keys:
    if (out/(key+'.npz')).is_file() and (out/(key+'.png')).is_file():
        with np.load(out/(key+'.npz')) as cache:
            if 'signature' in cache and str(cache['signature'])==signature:continue
    basis=axes((VIEWS|HOLDOUT)[key]);d=Vector(C[:3,:3]@basis[:,2]).normalized()
    s.camera.location=Vector(C[:3,:3]@CENTER)+d*11
    s.camera.rotation_euler=(-d).to_track_quat('-Z','Y').to_euler()
    exr=out/(key+'.exr');s.render.filepath=str(exr)
    bpy.ops.render.render(write_still=True)
    oi=oiio.ImageInput.open(str(exr));ch={};sub=0
    while oi.seek_subimage(sub,0):
        names=list(oi.spec().channelnames)
        a=oi.read_image(sub,0,0,len(names),oiio.FLOAT)
        for j,n in enumerate(names):ch[n]=a[:,:,j].copy()
        sub+=1
    oi.close()
    def read(layer,suffix):
        return np.stack([ch[next(n for n in ch if n.endswith('.'+layer+'.'+k))] for k in suffix],axis=-1)
    # Apply the scene's exact display transform when writing the beauty reference.
    result=bpy.data.images['Render Result'];s.render.image_settings.media_type='IMAGE';s.render.image_settings.file_format='PNG'
    s.render.image_settings.color_mode='RGBA';s.render.image_settings.color_depth='8'
    result.save_render(str(out/(key+'.png')),scene=s)
    s.render.image_settings.media_type='MULTI_LAYER_IMAGE';s.render.image_settings.file_format='OPEN_EXR_MULTILAYER';s.render.image_settings.color_depth='32'
    pos=read('Position','XYZ')@np.linalg.inv(C[:3,:3]).T
    norm=read('Normal','XYZ')@(C[:3,:3]/.02)
    subj=read('Object Index','X')[:,:,0].astype('B')
    np.savez_compressed(out/(key+'.npz'),pos=pos.astype('f'),n=norm.astype('f2'),kind=subj,
                        diffuse=read('Diffuse Color','RGB').astype('f2'),center=CENTER,scale=SCALE,signature=signature)
    print('Captured',key,'parts',np.unique(subj),flush=True)
    exr.unlink()

