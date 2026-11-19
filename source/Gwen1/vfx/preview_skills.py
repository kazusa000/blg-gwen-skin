"""Render gameplay-camera Q and W concepts with the approved Gwen model."""
from collections import deque
from pathlib import Path
import math
import sys
import os

import bpy
import json
import numpy as np
from mathutils import Vector, Quaternion

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from champion_layers import CUP_ALPHA, CUP_HALF_SIZE, CUP_YAW, CURRENT_SPEEDS, SEAL, q_shards, w_motes
OUT = HERE / 'preview-frames'
ART = HERE / 'art'
SKIN = HERE.parents[2] / 'skin' / 'Gwen1'
CAMERA = 'BLG Gwen · 游戏视角'
FRAME_FILTER = {int(i) for i in os.environ.get('GWEN_REVIEW_FRAMES','').split(',') if i}
ICE, ROSE, GOLD = (.06,.42,1.), (.96,.08,.48), (1.,.68,.34)


def image_material(name, path, strength, tint=None):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(str(path))
    image = bpy.data.images.load(str(path), check_existing=True)
    image.alpha_mode = 'STRAIGHT'
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    output = nodes.new('ShaderNodeOutputMaterial')
    texture = nodes.new('ShaderNodeTexImage')
    texture.image = image
    texture.extension = 'REPEAT'
    emission = nodes.new('ShaderNodeEmission')
    emission.inputs['Strength'].default_value = strength
    transparent = nodes.new('ShaderNodeBsdfTransparent')
    mix = nodes.new('ShaderNodeMixShader')
    color=texture.outputs['Color']
    if tint:
        multiply=nodes.new('ShaderNodeMixRGB')
        multiply.blend_type='MULTIPLY'
        multiply.inputs[0].default_value=1.
        multiply.inputs[2].default_value=(*tint,1.)
        links.new(texture.outputs['Color'],multiply.inputs[1])
        color=multiply.outputs[0]
    links.new(color, emission.inputs['Color'])
    opacity = nodes.new('ShaderNodeMath')
    opacity.operation = 'MULTIPLY'
    links.new(texture.outputs['Alpha'],opacity.inputs[0])
    links.new(nodes.new('ShaderNodeObjectInfo').outputs['Alpha'],opacity.inputs[1])
    links.new(opacity.outputs[0], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs['Surface'])
    return material, mix


def glow_material(name, color, strength):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color,1.)
    material.use_nodes = True
    nodes=material.node_tree.nodes
    nodes.clear()
    output=nodes.new('ShaderNodeOutputMaterial')
    light=nodes.new('ShaderNodeEmission')
    light.inputs['Color'].default_value=(*color,1.)
    light.inputs['Strength'].default_value=strength
    material.node_tree.links.new(light.outputs[0],output.inputs['Surface'])
    return material


def mesh_object(scene,name,material):
    mesh=bpy.data.meshes.new(name+' mesh')
    obj=bpy.data.objects.new(name,mesh)
    scene.collection.objects.link(obj)
    mesh.materials.append(material)
    return obj


class SpriteReview:
    def __init__(self, scene, camera, specs):
        self.camera=camera
        self.parts=[]
        materials={}
        for spec in specs:
            if spec.texture not in materials:
                materials[spec.texture]=image_material(spec.texture,ART/(spec.texture+'.png'),
                                                      1.35 if spec.glow else .96)[0]
            obj=mesh_object(scene,spec.name,materials[spec.texture])
            update_mesh(obj,[(-.5,-.5,0),(.5,-.5,0),(.5,.5,0),(-.5,.5,0)],
                        [(0,1,2,3)],[(0,0),(1,0),(1,1),(0,1)])
            obj.rotation_mode='QUATERNION'
            obj.scale=(spec.size[0]*.02,spec.size[1]*.02,1.)
            self.parts.append((spec,obj))
            # A rising crystal can overlap its successor at the same source.
            if spec.rate and spec.life*spec.rate>1:
                other=obj.copy();scene.collection.objects.link(other)
                self.parts.append((spec,other))

    def frame(self, elapsed, origin, gain=1., stop=None):
        previous=None
        for spec,obj in self.parts:
            clock=elapsed-spec.delay
            if spec.rate:
                last=int(math.floor(clock*spec.rate))
                if stop is not None:
                    last=min(last,int(math.floor((stop-spec.delay)*spec.rate)))
                emission=last-(1 if previous is spec else 0)
                age=clock-emission/spec.rate if emission>=0 else -1
            else:
                age=clock
            previous=spec
            obj.hide_render=age<0 or age>=spec.life or gain<=0
            if obj.hide_render:
                continue
            x,y,z=[p+age*v for p,v in zip(spec.origin,spec.speed)]
            obj.location=origin+Vector((x,-z,y))*.02
            obj.rotation_quaternion=(self.camera.rotation_euler.to_quaternion() @
                                     Quaternion((0,0,1),math.radians(spec.rotation+spec.spin*age)))
            t=age/spec.life
            if '_Silk_' in spec.name:
                unfold=np.interp(t,[0,.22,.65,1],[.18,.84,1,1.13])
                thickness=np.interp(t,[0,.22,.65,1],[.5,1.25,.9,.12])
                obj.scale=(spec.size[0]*.02*unfold,spec.size[1]*.02*thickness,1)
            opacity=np.interp(t,[0,.026,.97,1],[0,1,1,0]) if spec==SEAL else np.interp(t,[0,.1,.63,1],[0,1,.85,0])
            obj.color=(1,1,1,opacity*gain)


def update_mesh(obj,vertices,faces,uvs=None,materials=None,indices=None):
    obj.data.clear_geometry()
    obj.data.from_pydata(vertices,[],faces)
    obj.data.update()
    if materials:
        for mat in materials:
            if mat not in obj.data.materials:
                obj.data.materials.append(mat)
    if uvs and obj.data.polygons:
        layer=obj.data.uv_layers.active or obj.data.uv_layers.new(name='VFX')
        for polygon in obj.data.polygons:
            for loop in polygon.loop_indices:
                v=obj.data.loops[loop].vertex_index
                layer.data[loop].uv=uvs[v]
            if indices:
                polygon.material_index=indices[polygon.index]


def set_camera(scene,camera,target,distance,lens):
    direction=camera.rotation_euler.to_quaternion() @ Vector((0,0,1))
    camera.location=Vector(target)+direction*distance
    camera.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler()
    camera.data.type='PERSP'
    camera.data.lens=lens
    scene.camera=camera


def view_vector(camera):
    return camera.rotation_euler.to_quaternion() @ Vector((0,0,1))


def blade_tip(scene,rig,blade,jaw):
    deps=bpy.context.evaluated_depsgraph_get()
    evaluated=blade.evaluated_get(deps)
    coords=np.empty((len(evaluated.data.vertices),3),dtype='f')
    evaluated.data.vertices.foreach_get('co',coords.ravel())
    matrix=np.array(evaluated.matrix_world)
    coords=coords @ matrix[:3,:3].T + matrix[:3,3]
    arm=rig.evaluated_get(deps)
    pivot=np.array((arm.matrix_world @ arm.pose.bones['Scissors_'+jaw].matrix).translation)
    distance=np.linalg.norm(coords-pivot,axis=1)
    tip=coords[distance>distance.max()-.055].mean(axis=0)
    return Vector(tip)


def ribbon_mesh(obj,points,widths,toward_camera,tile_length=1.6):
    if len(points)<2:
        obj.hide_render=True
        return
    vertices,faces,uvs=[],[],[]
    distance=0.
    for i,point in enumerate(points):
        tangent=(points[min(i+1,len(points)-1)]-points[max(0,i-1)]).normalized()
        across=tangent.cross(toward_camera).normalized()
        if across.length<.1:
            across=tangent.cross(Vector((0,0,1))).normalized()
        width=widths[i]
        vertices.extend((tuple(point+across*width*.5),tuple(point-across*width*.5)))
        if i:
            k=i*2
            faces.append((k-2,k-1,k+1,k))
            distance+=(point-points[i-1]).length
        uvs.extend(((distance/tile_length,0.),(distance/tile_length,1.)))
    obj.hide_render=False
    update_mesh(obj,vertices,faces,uvs)


def smooth_path(points,subdivisions=3):
    if len(points)<3:
        return points
    result=[points[0]]
    extended=[points[0]]+points+[points[-1]]
    for i in range(1,len(extended)-2):
        p0,p1,p2,p3=extended[i-1:i+3]
        for j in range(1,subdivisions+1):
            t=j/subdivisions
            t2,t3=t*t,t*t*t
            value=(2*p1+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t2+
                   (-p0+3*p1-3*p2+p3)*t3)*.5
            result.append(value)
    return result


def q_frames():
    timeline=[(142+i,'first',i) for i in range(51)]
    timeline += [(290+i,'middle',i) for i in range(6)]
    timeline += [(296+i,'finish',i) for i in range(30)]
    return timeline


def fit_q_camera(scene,rig,camera,timeline):
    quaternion=camera.rotation_euler.to_quaternion()
    projected=[]
    for frame,_,_ in timeline:
        scene.frame_set(frame)
        arm=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        for name in ('Root','Head','L_Foot','R_Foot'):
            world=(arm.matrix_world@arm.pose.bones[name].matrix).translation
            projected.append(quaternion.inverted()@world)
        for name,jaw in [('Azure · ground crystal blade','A'),('Rose · ground crystal blade','B')]:
            projected.append(quaternion.inverted()@blade_tip(scene,rig,scene.objects[name],jaw))
    coords=np.array([tuple(point) for point in projected])
    low,high=coords.min(axis=0),coords.max(axis=0)
    center=Vector((low+high)*.5)
    width=high[0]-low[0]
    height=max(high[1]-low[1],width*560./620.)
    # Allow the ground-cast SCB meshes to extend to either side of the jaws.
    distance=max(10.,height*50./24.*1.58)
    camera.location=quaternion@center+(quaternion@Vector((0,0,1)))*distance
    camera.rotation_euler=quaternion.to_euler()
    camera.data.type='PERSP'
    camera.data.lens=50.


def render_q(scene,rig,camera):
    folder=OUT/'q-stitched'
    folder.mkdir(parents=True,exist_ok=True)
    trail_mat_blue,_=image_material('Q · ice-blue stitched crystal trail',ART/'q_blade_stitch.png',2.4,(.05,.34,.98))
    trail_mat_rose,_=image_material('Q · rose-pink stitched crystal trail',ART/'q_blade_stitch.png',2.4,(.96,.06,.42))
    star_mat,_=image_material('Q · final BLG star',ART/'q_final_star.png',2.6)
    azure=scene.objects['Azure · ground crystal blade']
    rose=scene.objects['Rose · ground crystal blade']
    blades={'Azure':(azure,'A',trail_mat_blue),'Rose':(rose,'B',trail_mat_rose)}
    trails={side:mesh_object(scene,'Q · '+side+' wake',material) for side,(_,_,material) in blades.items()}
    star=mesh_object(scene,'Q · four ray crystal',star_mat)
    # Native Gwen Q trail particles live for roughly half a second at 30fps.
    history={side:deque(maxlen=7) for side in blades}
    previous_stage=None
    timeline=q_frames()
    scene.render.engine='CYCLES'
    # A native additive sprite stack does not obscure lower layers. Cycles
    # needs enough transparent traversal depth for the equivalent card stack.
    scene.cycles.transparent_max_bounces=96
    scene.cycles.samples=8
    scene.cycles.use_denoising=True
    scene.render.resolution_x,scene.render.resolution_y=620,560
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGBA'
    fit_q_camera(scene,rig,camera,timeline)
    bursts=[(start,SpriteReview(scene,camera,list(q_shards(stage)))) for start,stage in
            ((0,'First'),(51,'Second'),(57,'Finisher'))]
    toward=view_vector(camera).normalized()
    for index,(frame,stage,tick) in enumerate(timeline):
        if stage!=previous_stage and tick==0:
            history={side:deque(maxlen=7) for side in blades}
        scene.frame_set(frame)
        ground=rig.matrix_world @ rig.pose.bones['Buffbone_Glb_Ground_Loc'].matrix.translation
        for start, burst in bursts:
            burst.frame((index-start)/30.,ground)
        tips={}
        for side,(blade,jaw,_) in blades.items():
            tip=blade_tip(scene,rig,blade,jaw)+toward*.045
            jaw_pivot=rig.matrix_world @ rig.pose.bones['Scissors_'+jaw].matrix.translation
            history[side].append((jaw_pivot.lerp(tip,.58),tip))
            tips[side]=tip
            if len(history[side])>1:
                # Sweep the blade surface between poses. Both edges have a
                # spatial anchor, including when the weapon reverses direction.
                inners=smooth_path([pair[0] for pair in history[side]])
                outers=smooth_path([pair[1] for pair in history[side]])
                vertices=[]; uvs=[]; faces=[]
                for i,(low,high) in enumerate(zip(inners,outers)):
                    u=i/(len(inners)-1)
                    vertices.extend((tuple(low),tuple(high)))
                    uvs.extend(((u,0),(u,1)))
                    if i:
                        k=2*i
                        faces.append((k-2,k-1,k+1,k))
                trails[side].hide_render=False
                update_mesh(trails[side],vertices,faces,uvs)
            else:
                trails[side].hide_render=True
        pulse=0.
        if stage=='finish':
            pulse=max(0.,1.-abs(tick-6)/4.)
        if pulse<.02:
            star.hide_render=True
        else:
            star.hide_render=False
            center=(tips['Azure']+tips['Rose'])*.5+toward*.1
            right=camera.rotation_euler.to_quaternion() @ Vector((1,0,0))
            up=camera.rotation_euler.to_quaternion() @ Vector((0,1,0))
            center+=toward*.055
            half=1.62*pulse
            vertices=[tuple(center-right*half-up*half),tuple(center+right*half-up*half),
                      tuple(center+right*half+up*half),tuple(center-right*half+up*half)]
            update_mesh(star,vertices,[(0,1,2,3)],[(0,0),(1,0),(1,1),(0,1)])
        # Spell1 holds the same pose at its tail while waiting for the next
        # game event. Keep the cast and finish beats for the review loop.
        if 17 <= index < 51 or (FRAME_FILTER and index not in FRAME_FILTER):
            previous_stage=stage
            continue
        scene.render.filepath=str(folder/f'{index:03}.png')
        bpy.ops.render.render(write_still=True)
        previous_stage=stage
        print('Q frame',index+1,'/',len(timeline),stage,tick,flush=True)
    for obj in (*trails.values(),star):
        obj.hide_render=True
    for _,burst in bursts:
        for _,obj in burst.parts:
            obj.hide_render=True
    return folder


def ring_mesh(obj,center,radius,progress,toward_camera,wall_height=3.25,uv_offset=0.):
    n=192
    live=max(.03,progress)
    r=radius*live
    vertices,faces,uvs=[],[],[]
    for i in range(n+1):
        angle=2*math.pi*i/n
        # Duplicate the U=0/U=1 endpoint so the ribbon UV seam stays local.
        # The actual Gwen mesh is a raised wall with one U turn around it.
        u=i/n-uv_offset
        for v in (0.,1.):
            vertices.append(tuple(center+Vector((math.cos(angle)*r,math.sin(angle)*r,wall_height*live*v))+toward_camera*.005))
            uvs.append((u,v))
        if i:
            k=2*i
            faces.append((k-2,k-1,k+1,k))
    obj.hide_render=progress<.025
    update_mesh(obj,vertices,faces,uvs)


def disc_mesh(obj,center,radius,toward_camera,segments=96):
    verts=[tuple(center+toward_camera*.012)]
    uvs=[(.5,.5)]
    for i in range(segments):
        angle=2*math.pi*i/segments
        x,y=math.cos(angle),math.sin(angle)
        verts.append(tuple(center+Vector((x*radius,y*radius,0))+toward_camera*.012))
        uvs.append((.5+.5*x,.5+.5*y))
    faces=[(0,1+i,1+(i+1)%segments) for i in range(segments)]
    update_mesh(obj,verts,faces,uvs)


def render_w(scene,rig,camera,radius):
    folder=OUT/'w-cup'
    folder.mkdir(parents=True,exist_ok=True)
    edge_mat,_=image_material('W · gold woven edge',ART/'w_outer_braid.png',1.4)
    mist_mat,mist_mix=image_material('W · airy blue pearl',ART/'w_mistfield.png',1.0)
    edge=mesh_object(scene,'W · embroidered ward ring',edge_mat)
    mist=mesh_object(scene,'W · soft mist field',mist_mat)
    lace=mesh_object(scene,'W · fine tread orbit',
                     image_material('W · orbit embroidery',ART/'w_stitch_orbit.png',1.32)[0])
    cup=mesh_object(scene,'W · Summoner’s Cup ground inlay',
                    image_material('W · silver trophy',ART/'w_worlds_cup.png',1.12)[0])
    w,h=(value*.02 for value in CUP_HALF_SIZE)
    update_mesh(cup,[(-w,-h,0),(w,-h,0),(w,h,0),(-w,h,0)],
                [(0,1,2,3)],[(0,0),(1,0),(1,1),(0,1)])
    cup.rotation_euler.z=math.radians(CUP_YAW)
    glint_mat,_=image_material('W · traveling gold sewing glint',ART/'w_sewing_glint.png',2.7)
    glint=mesh_object(scene,'W · traveling gold sewing glint',glint_mat)
    currents={shade:mesh_object(scene,'W · '+shade+' silk current',
                                image_material('W · '+shade+' moving weave',ART/f'w_current_{shade}.png',1.65)[0])
              for shade in CURRENT_SPEEDS}
    jewels=SpriteReview(scene,camera,[SEAL,*w_motes()])
    thread_mat,_=image_material('W · blue pink sewn thread',ART/'w_thread_trail.png',1.7)
    thread=mesh_object(scene,'W · scissors tip thread afterimage',thread_mat)
    thread_history=deque(maxlen=6)
    # Show the native cast, a short animated idle settling beat, then the
    # native exit transition. Emitter lifetime does not define GIF hold time.
    timeline=[(261+i,'cast',i) for i in range(29)]
    timeline += [(1+i,'settle',i) for i in range(24)]
    timeline += [(608+i,'fade',i) for i in range(8)]
    scene.render.engine='CYCLES'
    scene.cycles.transparent_max_bounces=96
    scene.cycles.samples=8
    scene.cycles.use_denoising=True
    scene.render.resolution_x,scene.render.resolution_y=620,500
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGBA'
    set_camera(scene,camera,(0.,-.2,2.0),28.,50.)
    toward=view_vector(camera).normalized()
    for index,(frame,stage,tick) in enumerate(timeline):
        scene.frame_set(frame)
        deps=bpy.context.evaluated_depsgraph_get()
        arm=rig.evaluated_get(deps)
        tip=arm.matrix_world @ arm.pose.bones['Buffbone_Scissors_A_Tip'].matrix.translation
        if stage=='cast':
            thread_history.append(Vector(tip)+toward*.07)
        else:
            thread_history.clear()
            thread.hide_render=True
        if stage=='cast' and len(thread_history)>1 and tick<14:
            trail_points=smooth_path(list(thread_history))
            widths=np.linspace(.02,.15,len(trail_points))
            ribbon_mesh(thread,trail_points,widths,toward,tile_length=1.3)
        else:
            thread.hide_render=True
        ground=arm.pose.bones['Buffbone_Glb_Ground_Loc'].matrix.translation
        center=Vector((ground.x,ground.y,.02))
        progress=min(1.,tick/8.) if stage=='cast' else 1.
        if stage=='fade':
            progress=1.-.10*tick/7.
        fade=max(0.,1.-tick/7.) if stage=='fade' else 1.
        edge.color=(1,1,1,fade)
        ring_mesh(edge,center,radius,progress,toward)
        disc_mesh(mist,center+Vector((0.,0.,.007)),radius*.98*max(.04,progress),toward)
        mist.hide_render=progress<.025
        glint.hide_render=stage!='cast' or tick>19
        if not glint.hide_render:
            sweep=tick/19.
            ring_mesh(glint,center,radius+.035,1.,toward,wall_height=3.25,uv_offset=sweep-.5)
        for shade,obj in currents.items():
            ring_mesh(obj,center,radius*(1.52 if shade=='ice' else 1.65)/1.8,progress,toward,
                      wall_height=3.25*(3.2 if shade=='ice' else 2.7)/2.,
                      uv_offset=-CURRENT_SPEEDS[shade]*index/30.)
            obj.color=(1,1,1,fade*min(index/5.,1.))
        jewels.frame(index/30.,center,fade,stop=53/30.)
        alpha=min(1.,tick/7.) if stage=='cast' else 1.
        if stage=='fade':
            alpha=max(0.,1.-tick/7.)
        mist.color=(1,1,1,.92*alpha)
        disc_mesh(lace,Vector((0,0,0)),radius*.96*progress,toward)
        lace.location=center+Vector((0,0,.032))
        lace.rotation_euler.z=math.radians(index/30.*9)
        lace.color=(1,1,1,.90*alpha)
        cup.location=center+Vector((0,0,.052))
        cup.color=(1,1,1,CUP_ALPHA*min(1.,index/(9*.032*30))*fade)
        if FRAME_FILTER and index not in FRAME_FILTER:
            continue
        scene.render.filepath=str(folder/f'{index:03}.png')
        bpy.ops.render.render(write_still=True)
        print('W frame',index+1,'/',len(timeline),stage,tick,flush=True)
    return folder


if __name__=='__main__':
    skill=sys.argv[-1]
    scene=bpy.context.scene
    rig=bpy.data.objects['BLG Gwen · Skin0']
    camera=bpy.data.objects[CAMERA]
    if skill in ('q','all'):
        render_q(scene,rig,camera)
    if skill in ('w','all'):
        meta=Path(ART/'w_effect_meta.json')
        radius=json.loads(meta.read_text(encoding='utf-8')).get('preview_radius_blender',8.4) if meta.exists() else 8.4
        render_w(scene,rig,camera,radius)
