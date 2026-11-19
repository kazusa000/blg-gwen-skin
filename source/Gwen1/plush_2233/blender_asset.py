"""Editable authoring rig: one pair driven from the original Gwen doll channels."""
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE=Path(__file__).resolve().parent
GAME=HERE.parents[2]/'skin'/'Gwen1'
DATA=HERE/'build'/'mesh.npz'
C3=np.array([[.02,0,0],[0,0,-.02],[0,.02,0]])
SCALE=.77
OFFSETS={22:-9.3,33:9.3}

def textile(kind='felt'):
    name='2233 · '+kind
    mat=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes=True
    tree=mat.node_tree;tree.nodes.clear()
    out=tree.nodes.new('ShaderNodeOutputMaterial');shader=tree.nodes.new('ShaderNodeBsdfPrincipled')
    tex=tree.nodes.new('ShaderNodeTexImage')
    tex.image=bpy.data.images.load(str(GAME/'textures/gwen-2233-plush.png'),check_existing=True)
    tex.image.reload();tex.image.pack()
    tree.links.new(tex.outputs['Color'],shader.inputs['Base Color'])
    values={'felt':(.92,0.,.13),'face':(.97,0.,.025),'gold thread':(.62,.08,.045),
            'enamel':(.46,.06,.055),'leather':(.78,0.,.035),'embroidery':(.88,0.,.035)}
    rough,metal,sheen=values[kind]
    shader.inputs['Roughness'].default_value=rough
    shader.inputs['Metallic'].default_value=metal
    shader.inputs['Sheen Weight'].default_value=sheen
    texture=tree.nodes.new('ShaderNodeTexNoise');texture.inputs['Scale'].default_value=620.
    bump=tree.nodes.new('ShaderNodeBump')
    bump.inputs['Distance'].default_value=.00016;bump.inputs['Strength'].default_value=.085
    tree.links.new(texture.outputs['Fac'],bump.inputs['Height']);tree.links.new(bump.outputs[0],shader.inputs['Normal'])
    tree.links.new(shader.outputs[0],out.inputs[0])
    return mat

def material_kind(tile):
    if tile.startswith('face'):return 'face'
    if tile=='gold':return 'gold thread'
    if tile in ('pink_gem','azure','pin_blue','pin_rose'):return 'enamel'
    if tile=='sole':return 'leather'
    if tile=='ink':return 'embroidery'
    return 'felt'

def install(rig,doll,collection):
    data=np.load(DATA)
    vs=data['vertices'];faces=data['triangles'];names=data['names'].tolist()
    prev=bpy.data.objects.get('2233 · paired puppet rig')
    if prev is not None:
        if not prev.get('gwen_2233_aux'):raise ValueError('Unexpected armature name collision')
        bpy.data.objects.remove(prev,do_unlink=True)
    bpy.context.view_layer.objects.active=rig
    if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    arm=bpy.data.armatures.new('2233 · companion pivots')
    aux=bpy.data.objects.new('2233 · paired puppet rig',arm)
    aux['gwen_2233_aux']=True;collection.objects.link(aux)
    aux.parent=rig
    bpy.context.view_layer.objects.active=aux
    aux.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    def add(name,source,scale,offset):
        src=rig.data.bones[source]
        eb=arm.edit_bones.new(name)
        eb.head=src.head_local*scale+offset;eb.tail=src.tail_local*scale+offset
        eb.align_roll(src.matrix_local.to_3x3().col[2])
        return eb
    add('Doll_Main','Doll_Main',1,Vector((0,0,0)))
    for n in (22,33):
        offset=Vector((OFFSETS[n]*.02,0,0))
        for name in [x for x in names if x.startswith(f'P{n}_')]:
            token=name.split('_',1)[1]
            src='Doll_Main' if token=='Base' else token
            eb=add(name,src,SCALE,offset)
            p=rig.data.bones[src].parent.name
            eb.parent=arm.edit_bones['Doll_Main' if token=='Base' else f'P{n}_'+('Base' if p=='Doll_Main' else p)]
    bpy.ops.object.mode_set(mode='OBJECT')
    constraint=aux.pose.bones['Doll_Main'].constraints.new('COPY_TRANSFORMS')
    constraint.target=rig;constraint.subtarget='Doll_Main'
    for pb in aux.pose.bones:
        if not pb.name.startswith(('P22_','P33_')) or pb.name.endswith('_Base'):continue
        source=pb.name.split('_',1)[1]
        for typ in ('COPY_ROTATION','COPY_SCALE'):
            k=pb.constraints.new(typ);k.target=rig;k.subtarget=source
            k.target_space='LOCAL';k.owner_space='LOCAL'
        for i in range(3):
            fc=pb.driver_add('location',i);driver=fc.driver
            var=driver.variables.new();var.name='d';var.type='SINGLE_PROP'
            var.targets[0].id=rig;var.targets[0].data_path=f'pose.bones["{source}"].location[{i}]'
            driver.expression=f'd*{SCALE}'
    mesh=bpy.data.meshes.new('22 and 33 · full fidelity Doll mesh')
    mesh.from_pydata((vs['p']@C3.T).tolist(),[],faces.tolist());mesh.update()
    mesh.polygons.foreach_set('use_smooth',np.ones(len(faces),bool))
    normal=np.array(vs['n']@C3.T);normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-12)
    mesh.normals_split_custom_set_from_vertices(normal.tolist())
    uvs=vs['uv'][faces].copy();uvs[:,:,1]=1-uvs[:,:,1]
    layer=mesh.uv_layers.new(name='2233 embroidery')
    layer.data.foreach_set('uv',uvs.astype('f').ravel())
    doll.data=mesh
    if 'face_tiles' in data.files:
        tile_types=data['face_tiles'].tolist()
        if len(tile_types)!=len(faces):raise ValueError('Doll face/material table mismatch')
        kinds=sorted(set(material_kind(tile) for tile in tile_types))
        mat_index={kind:i for i,kind in enumerate(kinds)}
        for kind in kinds:mesh.materials.append(textile(kind))
        mesh.polygons.foreach_set('material_index',np.asarray([mat_index[material_kind(x)] for x in tile_types],dtype=np.int32))
    else:
        mesh.materials.append(textile())
    doll.name='22 + 33 · Gwen marionettes'
    for mod in list(doll.modifiers):
        if mod.type=='ARMATURE':doll.modifiers.remove(mod)
    doll.vertex_groups.clear()
    slots=data['influences'][vs['i'][:,0]]
    for s in np.unique(slots):
        group=doll.vertex_groups.new(name=names[s]);group.add(np.flatnonzero(slots==s).tolist(),1,'REPLACE')
    for n in (22,33):
        ids=np.flatnonzero([names[i].startswith(f'P{n}_') for i in slots])
        doll.vertex_groups.new(name=f'Select {n}').add(ids.tolist(),1,'REPLACE')
    mod=doll.modifiers.new('22/33 native actions','ARMATURE');mod.object=aux
    doll['native_vertices']=len(vs);doll['native_triangles']=len(faces);doll['native_section']='Doll'
    image=bpy.data.images.load(str(GAME/'textures/gwen-2233-plush.png'),check_existing=True)
    doll['native_texture_size']=int(image.size[0])
    aux.show_in_front=False;aux.hide_render=True;aux.display_type='WIRE'
    bpy.context.view_layer.objects.active=rig
    aux.select_set(False)
    return doll,aux

