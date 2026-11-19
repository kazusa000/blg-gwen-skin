"""Read the rigged Blender doll and preserve its pre-quantization native vertex data."""
import sys
from pathlib import Path
import numpy as np
import bpy
from core import GW,C
from source_layout import OUT

def capture():
    sys.path.insert(0,str(GW/'plush_2233'))
    from blender_asset import material_kind
    doll,=(ob for ob in bpy.context.scene.objects if ob.get('native_section')=='Doll')
    mesh=doll.data
    with np.load(GW/'inputs/doll.npz') as data:
        v=data['vertices'];faces=data['triangles'];names=data['names'][data['influences']]
        tiles=data['face_tiles']
    pos=np.empty((len(mesh.vertices),3),'f');mesh.vertices.foreach_get('co',pos.ravel())
    assert np.array_equal(pos,(v['p']@C[:3,:3].T).astype('f')), 'Blender doll positions'
    corners=np.empty(len(mesh.loops),'i');mesh.loops.foreach_get('vertex_index',corners)
    assert np.array_equal(corners.reshape(-1,3),faces),'Blender doll topology'
    uv=np.empty((len(corners),2),'f');mesh.uv_layers.active.data.foreach_get('uv',uv.ravel())
    native_uv=v['uv'][corners].copy();native_uv[:,1]=1-native_uv[:,1]
    assert np.array_equal(uv,native_uv),'Blender doll UVs'
    normal=np.empty((len(corners),3),'f');mesh.corner_normals.foreach_get('vector',normal.ravel())
    authored=v['n'][corners]@(C[:3,:3].T/.02)
    alignment=(authored*normal).sum(1)
    assert alignment.min()>.993,('Blender doll corner normals',alignment.min())
    groups=[group.name for group in doll.vertex_groups]
    rig,=(m.object for m in doll.modifiers if m.type=='ARMATURE')
    deformers={b.name for b in rig.data.bones if b.use_deform}
    for vert in mesh.vertices:
        actual={groups[g.group]:round(g.weight,6) for g in vert.groups if g.weight>0 and groups[g.group] in deformers}
        expected={names[i]:round(float(w),6) for i,w in zip(v['i'][vert.index],v['w'][vert.index]) if w>0}
        assert actual==expected,('Doll joint weights',vert.index,actual,expected)
    mi=np.empty(len(mesh.polygons),'i');mesh.polygons.foreach_get('material_index',mi)
    material_names=[mat.name.split(' · ')[-1] for mat in mesh.materials]
    assert np.array_equal(np.asarray(material_names)[mi],[material_kind(t) for t in tiles])
    images={n.image for m in mesh.materials for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image}
    image,=images;assert image.packed_file and tuple(image.size)==(4096,4096)
    (OUT/'source-images/gwen-2233-plush.png').write_bytes(bytes(image.packed_file.data))
    np.savez(OUT/'doll-source.npz',v=v,f=faces)
    print('Blender doll verified',len(v),'vertices,',len(faces),'triangles,',len(material_names),'material regions',flush=True)
