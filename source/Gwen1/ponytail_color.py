"""Pearl ponytails with continuous, grouped rose and cyan highlights."""
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
SKIN=HERE.parents[1]/'skin'/'Gwen1'
ATLAS='gwen-hair-streaks.png'
DYES=[
    ('pearl blonde','E6D4DA','FFF6F5'),('champagne','E7D5D3','FFF7EF'),
    ('silver lilac','D6CDDE','FAF3FC'),('mauve shadow','BEAABD','EADCE7'),
    ('powder blue','4CB1E0','A0ECFF'),('glacier blue','287FC0','61D1FA'),
    ('petal pink','EC70A8','FFB6D5'),('orchid rose','CB4488','FF93C3')]


def rgb(value):
    return np.array(list(bytes.fromhex(value)))/255.


def linear(value):
    c=rgb(value)
    return np.where(c<=.04045,c/12.92,((c+.055)/1.055)**2.4)


def bake_cards():
    from PIL import Image
    old=SKIN/'textures'/'gwen-bound-hair.png'
    if not old.exists():old=HERE/'sources'/old.name
    with Image.open(old) as image:prior=np.array(image.convert('RGBA'))
    result=prior.copy()
    h,w=prior.shape[:2];cell=w//len(DYES)
    t=np.linspace(0,1,h)[:,None,None]
    for i,(_,root,tip) in enumerate(DYES):
        data=prior[:,i*cell:(i+1)*cell]
        intensity=data[:,:,:3].max(axis=2)
        grain=np.clip(intensity/np.median(intensity[data[:,:,3]>90]),.70,1.17)[:,:,None]
        paint=(1-t)*rgb(root)+t*rgb(tip)
        result[:,i*cell:(i+1)*cell,:3]=np.uint8(np.clip(paint*grain*255,0,255))
    target=SKIN/'textures'/ATLAS
    Image.fromarray(result).save(target)


def strand_material(bpy,idx):
    name,root,tip=DYES[idx]
    title='BLG ponytail · '+name
    mat=bpy.data.materials.get(title) or bpy.data.materials.new(title)
    mat.diffuse_color=(*linear(tip),1);mat.use_nodes=True
    nt=mat.node_tree;nt.nodes.clear();node=nt.nodes.new;link=nt.links.new
    data=node('ShaderNodeHairInfo')
    start=node('ShaderNodeAttribute');start.attribute_name='Dye at root'
    end=node('ShaderNodeAttribute');end.attribute_name='Dye at tip'
    travel=node('ShaderNodeMath');travel.operation='MULTIPLY_ADD';travel.inputs[1].default_value=.19
    link(data.outputs['Random'],travel.inputs[0]);link(data.outputs['Intercept'],travel.inputs[2])
    paint=node('ShaderNodeMixRGB');link(travel.outputs[0],paint.inputs[0])
    link(start.outputs['Color'],paint.inputs[1]);link(end.outputs['Color'],paint.inputs[2])
    strand=node('ShaderNodeBsdfHairPrincipled');strand.model='CHIANG';strand.parametrization='COLOR'
    strand.inputs['Roughness'].default_value=.24;strand.inputs['Radial Roughness'].default_value=.32
    strand.inputs['Coat'].default_value=.24;strand.inputs['Random Roughness'].default_value=.10
    link(paint.outputs[0],strand.inputs['Color'])
    diffuse=node('ShaderNodeBsdfDiffuse');diffuse.inputs['Roughness'].default_value=.39
    link(paint.outputs[0],diffuse.inputs['Color'])
    reflected=node('ShaderNodeMixShader');reflected.inputs[0].default_value=.40
    link(strand.outputs[0],reflected.inputs[1]);link(diffuse.outputs[0],reflected.inputs[2])
    soft=node('ShaderNodeEmission');link(paint.outputs[0],soft.inputs[0])
    finish=node('ShaderNodeMixShader');finish.inputs[0].default_value=.23
    link(reflected.outputs[0],finish.inputs[1]);link(soft.outputs[0],finish.inputs[2])
    out=node('ShaderNodeOutputMaterial');out.target='CYCLES';link(finish.outputs[0],out.inputs[0])
    preview=node('ShaderNodeBsdfPrincipled');preview.inputs['Roughness'].default_value=.29
    has_pigment=node('ShaderNodeMath');has_pigment.operation='GREATER_THAN';has_pigment.inputs[1].default_value=.001
    link(start.outputs['Fac'],has_pigment.inputs[0])
    shown=node('ShaderNodeMixRGB');shown.inputs[1].default_value=mat.diffuse_color
    link(has_pigment.outputs[0],shown.inputs[0]);link(paint.outputs[0],shown.inputs[2])
    link(shown.outputs[0],preview.inputs['Base Color']);link(shown.outputs[0],preview.inputs['Emission Color'])
    preview.inputs['Emission Strength'].default_value=.25
    out=node('ShaderNodeOutputMaterial');out.target='EEVEE';link(preview.outputs[0],out.inputs[0])
    return mat


def apply_color(bpy):
    scene=bpy.context.scene;scene.frame_set(1)
    lookup={name:i for i,(name,_,_) in enumerate(DYES)}
    mats=[strand_material(bpy,i) for i in range(len(DYES))]
    roots=np.array([[*linear(row[1]),1] for row in DYES],'f')
    tips=np.array([[*linear(row[2]),1] for row in DYES],'f')
    hair=[o for o in scene.objects if o.type=='CURVES' and 'interwoven ringlet fibres / ' in o.name]
    assert len(hair)==16
    dg=bpy.context.evaluated_depsgraph_get()
    counts=np.zeros(8,int)
    for ob in hair:
        data=ob.data;idx=lookup[ob.name.split(' / ')[-1]];n=len(data.curves)
        ids=np.full(n,idx,int)
        # Neighbouring fibre roots share their dye and retain it around the curl.
        points=np.empty((len(data.points),3),'f')
        ob.evaluated_get(dg).data.attributes['position'].data.foreach_get('vector',points.ravel())
        x,y,z=points.reshape(n,-1,3)[:,2:10].mean(axis=1).T
        side=.65 if ob.name.startswith('Left') else 2.5
        field=np.sin(67*x+36*y+17*z+side+.48*np.sin(31*z))+ .63*np.sin(27*y-39*z+side)
        if idx<4:
            ids[field<np.quantile(field,.08)]=4+(idx%2)
            ids[field>np.quantile(field,.92)]=6+(idx%2)
        else:
            low,high=np.quantile(field,[.43,.60])
            ids[(field>=low)&(field<=high)]=idx%3
        counts+=np.bincount(ids,minlength=8)
        for attr,colors in [('Dye at root',roots),('Dye at tip',tips)]:
            layer=data.attributes.get(attr) or data.attributes.new(attr,'FLOAT_COLOR','CURVE')
            layer.data.foreach_set('color',np.ascontiguousarray(colors[ids]).ravel())
        data.materials[0]=mats[idx];data.update_tag()
        card=scene.objects['Cards · '+ob.name];me=card.data
        per_card=35*3;count=len(me.vertices)//per_card
        take=np.linspace(0,n-1,count,dtype=int)
        corner=np.empty(len(me.loops),'i');me.loops.foreach_get('vertex_index',corner)
        uv=me.uv_layers['Longitudinal strands'];coord=np.empty((len(me.loops),2),'f')
        uv.data.foreach_get('uv',coord.ravel())
        coord[:,0]=(np.mod(coord[:,0]*8,1)+ids[take][corner//per_card])/8
        uv.data.foreach_set('uv',coord.ravel());me.update()
    atlas=bpy.data.images.load(str(SKIN/'textures'/ATLAS),check_existing=True)
    atlas.pack();atlas.filepath='//textures/'+ATLAS
    mat=bpy.data.materials['BLG · baked strand cards']
    next(n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE').image=atlas
    portrait=bpy.data.images['turnaround-v1.png'];assert portrait.packed_file
    for packed in portrait.packed_files:packed.filepath=str(SKIN/'textures'/'turnaround-v1.png')
    portrait.filepath='//textures/turnaround-v1.png'
    print('Ponytail fibres by colour:',counts.tolist(),flush=True)


def finish_scene(bpy):
    from mathutils import Vector
    scene=bpy.context.scene
    apply_color(bpy)
    title='09 · 设计参考'
    refs=bpy.data.collections.get(title)
    if refs is None:
        refs=bpy.data.collections.new(title);scene.collection.children.link(refs)
    for file,name,x,size in [('character-turnaround.png','格温 · 人物三视图',-5,5.2),
                              ('scissors.png','剪刀 · 当前参考',5,3.7)]:
        source=bpy.data.images.load(str(SKIN/'reference'/file),check_existing=True)
        source.pack()
        for packed in source.packed_files:packed.filepath=str(SKIN/'reference'/file)
        source.filepath='//reference/'+file
        ob=refs.objects.get(name)
        if ob is None:
            ob=bpy.data.objects.new(name,None);refs.objects.link(ob)
        ob.empty_display_type='IMAGE';ob.data=source;ob.empty_display_size=size
        ob.rotation_euler=(np.pi/2,0,0);ob.location=(x,.8,1.85);ob.hide_render=True
    refs.hide_render=True;refs.hide_viewport=True
    # All character maps stay reloadable when this file is built from the source folder.
    for im in bpy.data.images:
        if im.source=='FILE' and im.users and im.packed_file and (SKIN/'textures'/im.name).is_file():
            for packed in im.packed_files:packed.filepath=str(SKIN/'textures'/im.name)
            im.filepath='//textures/'+im.name
    stage=next(c for c in scene.collection.children if c.name.startswith('08'))
    name='BLG Gwen · 游戏视角'
    cam=stage.objects.get(name)
    if cam is None:
        data=bpy.data.cameras.new(name);cam=bpy.data.objects.new(name,data);stage.objects.link(cam)
    direction=Vector((.30,-1,.64)).normalized();target=Vector((-.12,-.05,1.78))
    cam.location=target+12*direction;cam.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler()
    cam.data.type='ORTHO';cam.data.ortho_scale=4.08;scene.camera=cam
    scene.render.resolution_x=680;scene.render.resolution_y=820;scene.render.resolution_percentage=100
    scene.render.filepath='//Gwen1-render.png'


def verify(bpy):
    import hashlib
    scene=bpy.context.scene
    assert (scene.frame_start,scene.frame_end)==(1,289)
    assert scene.get('portrait_eyes')=='reference'
    refs=scene.collection.children['09 · 设计参考']
    assert {o.data.name for o in refs.objects}=={'character-turnaround.png','scissors.png'}
    assert refs.hide_render and refs.hide_viewport
    maps=set()
    for im in bpy.data.images:
        if im.source!='FILE' or not im.users:continue
        target=Path(bpy.path.abspath(im.filepath)).resolve()
        assert target.is_relative_to(SKIN) and target.is_file(),(im.name,target)
        assert im.packed_file and len(im.packed_files)==1
        packed=im.packed_files[0]
        assert Path(bpy.path.abspath(packed.filepath)).resolve()==target,(im.name,packed.filepath)
        assert hashlib.sha256(packed.packed_file.data).digest()==hashlib.sha256(target.read_bytes()).digest(),im.name
        if target.parent==SKIN/'textures':maps.add(target.name)
    assert maps=={p.name for p in (SKIN/'textures').iterdir() if p.is_file()},maps
    palette=np.array([linear(row[1]) for row in DYES])
    counts=np.zeros(8,int)
    locks=[o for o in scene.objects if o.type=='CURVES' and 'ringlet fibres / ' in o.name]
    assert len(locks)==16
    for lock in locks:
        vals=np.empty((len(lock.data.curves),4),'f')
        lock.data.attributes['Dye at root'].data.foreach_get('color',vals.ravel())
        diff=np.linalg.norm(vals[:,None,:3]-palette,axis=-1);ids=np.argmin(diff,axis=1)
        assert diff.min(1).max()<1e-4
        counts+=np.bincount(ids,minlength=8)
        cards=scene.objects['Cards · '+lock.name]
        uv=cards.data.uv_layers['Longitudinal strands'];corners=np.empty((len(uv.data),2),'f');uv.data.foreach_get('uv',corners.ravel())
        points=np.empty(len(corners),'i');cards.data.loops.foreach_get('vertex_index',points)
        sampled=ids[np.linspace(0,len(ids)-1,len(cards.data.vertices)//105,dtype=int)]
        assert np.array_equal(np.floor(corners[:,0]*8).astype(int),sampled[points//105])
    print('Verified packed maps and references, all 16 groom and card pairs. White / cyan / pink:',
          counts[:4].sum(),counts[4:6].sum(),counts[6:].sum(),flush=True)


if __name__=='__main__':
    import sys
    if '--atlas' in sys.argv:
        bake_cards()
    elif '--verify' in sys.argv:
        import bpy
        verify(bpy)
    else:
        import bpy
        finish_scene(bpy)
        bpy.context.preferences.filepaths.save_version=0
        bpy.data.orphans_purge(do_recursive=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(SKIN/'Gwen1-BLG.blend'),compress=True,relative_remap=False)
