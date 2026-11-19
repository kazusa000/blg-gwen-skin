"""Read production meshes in rest space. Curves use their original rigged carriers."""
from pathlib import Path
import json,hashlib,sys
import numpy as np
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from core import C,Gwen,WORK,clip,world
from source_layout import SOURCE,OUT,TILES,VIEWS,ATLAS,WEAPON_SIZE,WEAPON_CROPS,coords
from fidelity_cameras import axes,CENTER,SCALE,HEIGHT,WIDTH,VIEWS as EYES
from ponytail_color import DYES,linear
assert Path(bpy.data.filepath).resolve()==SOURCE.resolve()
from source_weights import raw,vertdata,weight_stats
scene=bpy.context.scene;scene.frame_set(1)
rig=next(ob for ob in scene.objects if ob.type=='ARMATURE' and 'Skin0' in ob.name)
rig.data.pose_position='REST';dg=bpy.context.evaluated_depsgraph_get();dg.update()
out=OUT/'parts';out.mkdir(exist_ok=True,parents=True)
images=OUT/'source-images';images.mkdir(exist_ok=True)
image_hashes={}
for name in ('turnaround-v1.png','gwen-corset.png','gwen-mantle-silk.png','gwen-hair-streaks.png','gwen-train-crest.png','scissors.png'):
    image=bpy.data.images[name]
    data=bytes(image.packed_file.data) if image.packed_file else Path(bpy.path.abspath(image.filepath)).read_bytes()
    (images/name).write_bytes(data);image_hashes[name]=hashlib.sha256(data).hexdigest()
rows=[];swatches={};mapped_walls=0;maps={}
g=Gwen();pose=world(clip(g,'idle')[0],g.parents)@np.linalg.inv(g.bind)
def normalized(v):return v/np.maximum(1e-10,np.linalg.norm(v,axis=-1,keepdims=True))
def save(name,role,v,f,**info):
    assert np.isfinite(v['p']).all() and np.isfinite(v['uv']).all()
    assert np.allclose(v['w'].sum(axis=-1),1,atol=1e-5)
    idx=len(rows);np.savez(out/f'{idx:03d}.npz',v=v,f=f.astype('i4'))
    rows.append(dict(name=name,role=role,file=f'{idx:03d}.npz',triangles=len(f),**info))
def solid(mat):
    if mat.name not in swatches:
        tree=mat.node_tree
        bs=next((n for n in tree.nodes if n.type=='BSDF_PRINCIPLED'),None) if tree else None
        color=bs.inputs['Base Color'].default_value[:3] if bs else mat.diffuse_color[:3]
        swatches[mat.name]=dict(idx=len(swatches),linear=list(color))
    sw=swatches[mat.name]['idx'];return np.array([4180+sw%6*64,40+(sw//6)*64])/ATLAS
def layer(me,node,loops):
    link=node.inputs[0].links
    name=getattr(link[0].from_node,'uv_map','') if link else ''
    uv=me.uv_layers.get(name) or me.uv_layers.active
    assert uv,(me.name,node.name)
    return raw(uv.data,'uv',(len(me.loops),2))[loops]*[1,-1]+[0,1]
def attr(me,key,ids,fallback):
    at=me.attributes.get(key)
    return raw(at.data,'value',len(me.vertices))[ids] if at else np.broadcast_to(fallback,ids.shape)
def projected(v,ids,family):
    # Project the original fine fur onto the exact underlying weighted surface.
    sm=np.einsum('vk,vkij->vij',v['w'],pose[g.influences[v['i']]])
    pp=(sm[:,:3,:3]@v['p'][...,None])[...,0]+sm[:,:3,3]
    nn=normalized((sm[:,:3,:3]@v['n'][...,None])[...,0])
    pt=pp[ids].mean(1);norm=normalized(nn[ids].mean(1))
    scores=[];uvs=[]
    for key in VIEWS:
        data=maps[family,key];hh,ww=data['kind'].shape
        axis=axes(EYES[key]);uv=(pp-data['center'])@axis[:,:2]*(hh/float(data['scale']))/[ww,hh]+.5
        ij=np.clip((uv[ids].mean(1)*[ww,hh]).astype(int),[0,0],[ww-1,hh-1])
        x,y=ij.T
        dist=np.linalg.norm(pt-data['pos'][y,x],axis=1)
        valid=np.isin(data['kind'][y,x],[4,14] if family=='pile' else [5,15])
        score=np.abs(norm@axis[:,2])-.34*np.minimum(dist,35)-4*(~valid)
        if family=='face' and key=='front':
            score+=.25*((norm@axis[:,2]>.4)&(dist<.42))
        scores.append(score);uvs.append(coords(TILES[family+'/'+key],uv[ids].clip(0,1)))
    select=np.argmax(scores,axis=0);return np.array(uvs)[select,np.arange(len(ids))]
def weapon_wall(ob,mat,pts):
    key={'Rose gold bevel':'gold','Smoky titanium':'steel','Sapphire edge':'blue','Tourmaline edge':'pink','Violet enamel face':'ink'}[mat.name.split(' / ')[1]]
    # One longitudinal coordinate for the entire casting, including both bevels.
    # Neighbouring wall triangles must meet at exactly the same texel.
    flat=pts.reshape(-1,3);lo,hi=flat.min(0),flat.max(0);q=(pts-lo)/np.maximum(hi-lo,1.e-7)
    tri_n=np.abs(np.cross(pts[:,1]-pts[:,0],pts[:,2]-pts[:,0]))
    run=pts[:,:,2]+.413713*pts[:,:,1]
    uv=np.stack(((run-run.min())/max(np.ptp(run),1e-8),q[:,:,0]),axis=-1)
    a,b=uv[:,1]-uv[:,0],uv[:,2]-uv[:,0]
    caps=np.abs(a[:,0]*b[:,1]-a[:,1]*b[:,0])<1e-12
    for axis,(u,vv) in enumerate(((2,1),(2,0),(1,0))):
        use=caps&(tri_n.argmax(1)==axis);uv[use]=q[use][:,:,[u,vv]]
    a,b=uv[:,1]-uv[:,0],uv[:,2]-uv[:,0];area=np.abs(a[:,0]*b[:,1]-a[:,1]*b[:,0])
    assert np.all((area>1e-12)|(tri_n.max(1)<1.e-7)),(ob.name,area.min())
    return coords(TILES['wall/'+key],uv,WEAPON_SIZE)
for family in ('pile','face'):
    for key in VIEWS:
        with np.load(OUT/family/(key+'.npz')) as d:maps[family,key]={k:d[k] for k in ('pos','kind','center','scale')}
for col in scene.collection.children:
    if col.hide_render or col.name[:2] not in ('01','02','03','04','05','06','07'):continue
    role='Scissors' if col.name[:2]=='07' else 'Body'
    for ob in col.objects:
        if ob.hide_render or ob.name.startswith('Cards · '):continue
        if ob.type!='MESH':raise ValueError(ob.name)
        assert np.allclose(np.asarray(ob.matrix_world),np.eye(4),atol=.0001),ob.name
        ev=ob.evaluated_get(dg);me=ev.to_mesh(preserve_all_data_layers=True,depsgraph=dg)
        me.calc_loop_triangles()
        v=vertdata(ob,me);ids=raw(me.loop_triangles,'vertices',(len(me.loop_triangles),3),'i')
        loops=raw(me.loop_triangles,'loops',ids.shape,'i')
        mi=raw(me.loop_triangles,'material_index',len(ids),'i')
        outv=v[ids]
        cn=raw(me.corner_normals,'vector',(len(me.loops),3))
        outv['n']=normalized(cn[loops]@(np.linalg.inv(C[:3,:3])/50).T)
        # Several authored ring surfaces face inward. Blender lights their backfaces;
        # a native lit skin uses the exported normal, including on two-sided cloth.
        xyz=v['p'][ids]
        area=np.cross(xyz[:,1]-xyz[:,0],xyz[:,2]-xyz[:,0])
        term=(area*(xyz.mean(1)-(v['p'].min(0)+v['p'].max(0))*.5)).sum(1)
        inward=term.sum()<-.55*np.abs(term).sum()
        if inward:outv['n']*=-1;v['n']*=-1
        for j in np.unique(mi):
            use=mi==j;mt=me.materials[j]
            nodes=[n for n in mt.node_tree.nodes if n.type=='TEX_IMAGE' and n.image] if mt.node_tree else []
            if mt.name.startswith('Ermine'):
                outv['uv'][use]=projected(v,ids[use],'pile');continue
            if ob.name.startswith(('Coiffed head','Lifted fringe lock')):
                outv['uv'][use]=projected(v,ids[use],'face');continue
            if mt.name=='Embroidered bodice panels':
                uv=layer(me,nodes[0],loops);lo=uv.min((0,1));extent=uv.max((0,1))-lo
                surface=(uv-lo)/extent
                np.savez(OUT/'corset-layers.npz',surface=surface,under=uv,over=layer(me,nodes[1],loops),mix=attr(me,'Front panel',ids,0))
                outv['uv'][use]=coords(TILES['bodice'],surface[use]);continue
            if role=='Scissors' and not nodes:
                outv['uv'][use]=weapon_wall(ob,mt,v['p'][ids[use]].astype(float));mapped_walls+=use.sum();continue
            if not nodes or not me.uv_layers:
                outv['uv'][use]=solid(mt);continue
            selection=np.zeros(len(ids),'i')
            if len(nodes)==3:
                main=attr(me,'Main weight',ids,1).mean(1);rear=attr(me,'Rear weight',ids,0).mean(1)
                selection=np.where(main<.5,1,np.where(rear>.5,2,0))
            for k,node in enumerate(nodes):
                pick=use&(selection==k)
                if not pick.any():continue
                name='weapon/'+mt.name.split(' / ')[1] if role=='Scissors' else node.image.name
                assert name in TILES,(ob.name,name)
                uv=layer(me,node,loops[pick]).clip(0,1)
                if role=='Scissors':
                    x0,y0,x1,y1=WEAPON_CROPS[mt.name.split(' / ')[1]]
                    uv=(uv*[887,1774]-[x0+.5,y0+.5])/[x1-x0-1,y1-y0-1]
                    assert uv.min()>=0 and uv.max()<=1,(ob.name,mt.name)
                outv['uv'][pick]=coords(TILES[name],uv,WEAPON_SIZE if role=='Scissors' else ATLAS)
        if inward:outv=outv[:,::-1]
        vv,idx=np.unique(outv.reshape(-1),return_inverse=True)
        save(ob.name,role,vv,idx.reshape(-1,3),source_faces=len(ids),source_vertices=len(v),kind='mesh',
             normals_corrected=bool(inward),materials=[m.name for m in me.materials])
        np.save(out/(str(len(rows)-1).zfill(3)+'-materials.npy'),mi.astype('u1'))
        ev.to_mesh_clear()
print('All evaluated surface meshes exported',len(rows),flush=True)
palette=np.array([linear(root) for _,root,_ in DYES])
for col in scene.collection.children:
    if not col.name.startswith('11'):continue
    baked=[]
    for ob in col.objects:
        if ob.type!='CURVES' or ob.hide_render:continue
        d=ob.data;ns=len(d.curves);steps=len(d.points)//ns
        if 'ringlet' not in ob.name and 'swept nape' not in ob.name:
            baked.append(dict(name=ob.name,points=len(d.points),strands=ns));continue
        carrier=scene.objects['Weights / '+ob.name]
        v=vertdata(carrier,carrier.data).reshape(ns,steps)
        radius=raw(d.attributes['radius'].data,'value',(ns,steps))/.02
        assert np.all(radius>=0)
        points=v['p'].astype(float)
        tangent=normalized(np.gradient(points,axis=1))
        # Alternating edges form a continuous two-sided ribbon. Every original knot
        # contributes its position, width and skin weights, including the two tips.
        # Orient the native ribbon in the approved idle pose, then transform its
        # normal and width back into bind space for the full animation library.
        sm=np.einsum('...k,...kij->...ij',v['w'],pose[g.influences[v['i']]])
        position=np.einsum('...ij,...j->...i',sm[:,:,:3,:3],points)+sm[:,:,:3,3]
        direction=normalized(np.gradient(position,axis=1))
        angle=.72*np.sin(np.arange(ns)[:,None,None]*1.678)
        plane=normalized(np.concatenate((np.sin(angle),np.ones_like(angle)*.39,np.cos(angle)),axis=2))
        posed_edge=normalized(np.cross(direction,plane))
        edge=normalized(np.linalg.solve(sm[:,:,:3,:3],posed_edge[...,None])[...,0])
        normal=normalized(np.linalg.solve(sm[:,:,:3,:3],normalized(np.cross(posed_edge,direction))[...,None])[...,0])
        sign=np.where(np.arange(steps)%2,1.,-1.)
        v['p']=points+sign[None,:,None]*radius[:,:,None]*edge
        v['n']=normal
        dye=ob.name.split(' / ')[-1]
        colors=raw(d.attributes['Dye at root'].data,'color',(ns,4))[:,:3] if 'Dye at root' in d.attributes else None
        idx=np.argmin(np.linalg.norm(colors[:,None]-palette[None],axis=2),axis=1) if colors is not None else np.full(ns,[n for n,_,_ in DYES].index(dye))
        t=np.broadcast_to(np.linspace(0,1,steps),radius.shape)
        # The broad reflection moves with the original sculpted bend. Each fibre
        # retains its root dye and slight within-lock value variation.
        shade=np.clip(.37+.40*(1-direction[:,:,1]**2)+.11*np.sin(np.arange(ns)[:,None]*1.618)+.06*t,0,1)
        uv=np.stack((t,shade),axis=-1)
        for shade_id in np.unique(idx):v['uv'][idx==shade_id]=coords(TILES['dye/'+str(shade_id)],uv[idx==shade_id])
        ends=v[:,[0,-1]].copy();ends['p']=points[:,[0,-1]]-sign[[0,-1]][None,:,None]*radius[:,[0,-1],None]*edge[:,[0,-1]]
        vv=np.concatenate((v,ends),axis=1)
        rr=steps+2;k=np.arange(steps-2)
        f=np.column_stack((k,k+1,k+2));f[1::2]=f[1::2,::-1]
        f=np.vstack(([steps,0,1],f,[steps-2,steps-1,steps+1]))
        f=(f[None]+(np.arange(ns)*rr)[:,None,None]).reshape(-1,3)
        save(ob.name,'Body',vv.ravel(),f,kind='fibre',strands=ns,knots=len(d.points))
from doll_source import capture
capture()
image_hashes['gwen-2233-plush.png']=hashlib.sha256((images/'gwen-2233-plush.png').read_bytes()).hexdigest()
(OUT/'source.json').write_text(json.dumps(dict(source_sha=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),images=image_hashes,parts=rows,pile=baked,weight_stats=weight_stats,swatches=swatches,wall_triangles=int(mapped_walls)),ensure_ascii=False),'utf8')
print('Finished source geometry',len(rows),'textured wall triangles',mapped_walls,flush=True)

