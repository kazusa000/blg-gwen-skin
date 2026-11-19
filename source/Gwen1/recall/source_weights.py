"""Transfer the authored Blender deform groups to the production skin's joint palette."""
from core import C, GW, Gwen
import numpy as np
D=np.load(GW/'inputs/recall.npz')
names=D['names'].tolist()
parents=D['parents']
slots={names[j]:i for i,j in enumerate(D['inf'])}
dtype=Gwen().verts.dtype
weight_stats={'vertices_over_four':0,'max_omitted_weight':0.}

def raw(seq,field,shape,t='f'):
    a=np.empty(shape,t);seq.foreach_get(field,a.ravel());return a

def slot(name):
    j=names.index(name)
    while names[j] not in slots:
        j=parents[j];assert j>=0,name
    return slots[names[j]]

def vertdata(ob,me):
    v=np.zeros(len(me.vertices),dtype=dtype)
    p=raw(me.vertices,'co',(len(v),3));rot=np.linalg.inv(C[:3,:3])
    v['p']=p@rot.T;v['n']=raw(me.vertices,'normal',(len(v),3))@(rot/50).T
    mapping={g.index:slot(g.name) for g in ob.vertex_groups if g.name in names}
    for i,pt in enumerate(me.vertices):
        ww={}
        for w in pt.groups:
            if w.group in mapping and w.weight>.00001:
                bone=mapping[w.group];ww[bone]=ww.get(bone,0)+w.weight
        ordered=sorted(ww.items(),key=lambda pair:-pair[1])
        if len(ordered)>4:
            weight_stats['vertices_over_four']+=1
            dropped=sum(val for _,val in ordered[4:])/sum(ww.values())
            weight_stats['max_omitted_weight']=max(weight_stats['max_omitted_weight'],dropped)
        use=ordered[:4]
        if not use:
            raise ValueError(f'No weighted joint on {ob.name}, vertex {i}')
        ids,weights=zip(*use);v['i'][i,:len(ids)]=ids;v['w'][i,:len(ids)]=np.array(weights)/sum(weights)
    return v
