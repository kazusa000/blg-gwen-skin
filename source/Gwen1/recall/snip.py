"""One shared axle with hand-seated rings and a deliberately authored blade closure."""
from core import *
def align(a,b):
    a=unit(a);b=unit(b);v=np.cross(a,b);c=np.clip(a@b,-1,1)
    if np.linalg.norm(v)<1e-8:return np.eye(3) if c>0 else rot(np.cross(a,[1,0,0]) if abs(a[0])<.9 else np.cross(a,[0,1,0]),np.pi)
    return rot(v,np.arccos(c))
def cuts(g):
    data=np.load(GW/'inputs/approved-q.npz');base=data['pose'];palms=data['palm_weights']
    seats=data['seats'];sockets=data['sockets'];ii=g.names.index;Cinv=np.linalg.inv(C);ib=np.linalg.inv(g.bind)
    def centres(w):
        deform=C@w@ib@Cinv
        return (np.einsum('jab,hjb->ha',deform,palms)@Cinv.T)[:,:3]
    def point(mat,p):return mat[:3,:3]@p+mat[:3,3]
    out=[];contacts=[]
    for i,ang in enumerate([21,25,31,34,21,.9,1.8,11,19,24,26,27,27,27]):
        L=mix(base[0],base[5],.56) if i in (5,6) else base[i].copy()
        w=world(L,g.parents);cent=centres(w);scale=.64
        # Tide the blade slightly down into the textile while the arms thrust.
        pole=rot([1,0,0],.30 if i in (5,6) else .14)@rot([0,0,1],-.13)
        turns=[pole@rot([0,1,0],sign*np.deg2rad(ang)) for sign in (1,-1)]
        ring=np.array([r@p*scale for r,p in zip(turns,seats)])
        hinge=cent.mean(0)-ring.mean(0)
        for h,side in enumerate('LR'):
            iw,ie,ish=[ii(side+'_'+j) for j in ('Hand','Elbow','Shoulder')]
            A,B,H=w[[ish,ie,iw],:3,3];goal=H+hinge+ring[h]-cent[h]
            arm1=np.linalg.norm(B-A);arm2=np.linalg.norm(H-B)
            line=unit(goal-A);dist=np.clip(np.linalg.norm(goal-A),abs(arm1-arm2)+.01,arm1+arm2-.01)
            along=(dist*dist+arm1*arm1-arm2*arm2)/(2*dist)
            bend=B-A-line*((B-A)@line)
            E=A+line*along+unit(bend)*np.sqrt(max(0,arm1*arm1-along*along))
            R=align(B-A,E-A);X=w[ish].copy();X[:3,:3]=R@X[:3,:3];L[ish]=np.linalg.inv(w[g.parents[ish]])@X
            now=world(L,g.parents);E=now[ie,:3,3];H=now[iw,:3,3]
            X=now[ie].copy();X[:3,:3]=align(H-E,goal-E)@X[:3,:3];L[ie]=np.linalg.inv(now[g.parents[ie]])@X
            now=world(L,g.parents);X=w[iw].copy();X[:3,3]=now[iw,:3,3];L[iw]=np.linalg.inv(now[g.parents[iw]])@X
        new=world(L,g.parents);actual=centres(new)
        # Fine adjustment of the wrist, below a few native units whenever the target is reachable.
        for h,side in enumerate('LR'):
            j=ii(side+'_Hand');delta=hinge+ring[h]-actual[h]
            L[j,:3,3]+=np.linalg.solve(new[g.parents[j],:3,:3],delta)
        ja,jb=ii('Scissors_A'),ii('Scissors_B')
        wa=trs(hinge,turns[0],scale)@g.bind[ja];wb=trs(hinge,turns[1],scale)@g.bind[jb]
        L[ja]=wa;L[jb]=np.linalg.inv(wa)@wb
        contact=hinge+.76*sum((turns[h]@sockets[h]*scale for h in range(2)))/2
        gap=np.linalg.norm(hinge+turns[0]@sockets[0]*scale-(hinge+turns[1]@sockets[1]*scale))
        out.append(L);contacts.append(contact)
        if i==5:print('Closed tip gap',round(gap,2),'contact',contact.round(1),'grip errors',np.linalg.norm(centres(world(L,g.parents))-hinge-ring,axis=1).round(2))
    return np.array(out),contacts[5]

