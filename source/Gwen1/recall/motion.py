"""Choreography at native 30 Hz, in Gwen skeleton local coordinates."""
from core import *
from math import pi
from props import build
from snip import cuts
sys.path.insert(0,str(GW/'plush_2233'))
from native import extend_rig

def choreograph():
    g=Gwen();_,names,inf,_,parents,bind=extend_rig(g)
    props=build()
    extra=['Stage','Cup','Change']+[v+str(i) for i in range(4) for v in ['Badge','Silk','Burst','Dash']]+['Tail'+str(i)+str(h) for i in range(4) for h in (0,1)]
    names=names+['RC_'+n for n in extra];parents=np.r_[parents,[-1]*len(extra)]
    bind=np.concatenate([bind,np.tile(np.eye(4),(len(extra),1,1))])
    rest=bind.copy()
    for j,p in enumerate(parents):
        if p>=0:rest[j]=np.linalg.inv(bind[p])@bind[j]
    ix={s:i for i,s in enumerate(names)}
    for n in extra: 
        if not n.startswith('Badge'):inf.append(ix['RC_'+n])
    source={n:clip(g,n) for n in ('idle','joke_start')}
    yaw=lambda a:rot((0,1,0),a)
    root=ix['Root'];sc=ix['Scissors_A'];pel=ix['Pelvis']
    moving=[i for i,p in enumerate(g.parents) if p<0 and g.names[i]!='Doll_Root']
    source['spell1'],blade=cuts(g)
    positions=[];angles=[]
    for j,a in enumerate(ANCHORS):
        outward=-inward(a);side=unit(np.cross([0,1,0],outward))
        look=unit(outward*.72+side*.69)
        ang=np.arctan2(look[0],look[2]);angles.append(ang)
        contact=a+inward(a)*LENGTH*.55
        contact[1]-=24
        offset=contact-yaw(ang)@blade
        positions.append(offset)
    def placed(m,ang,off):
        b=m.copy();b[moving]=trs(off,yaw(ang))@b[moving];return b
    def world_joint(local,parents,j):
        chain=[]
        while j>=0:chain.append(j);j=parents[j]
        a=np.eye(4)
        for k in chain[::-1]:a=a@local[k]
        return a
    def turn(local,j,axis,angle):
        p=parents[j];base=world_joint(local,parents,p) if p>=0 else np.eye(4)
        w=base@local[j];w[:3,:3]=rot(axis,angle)@w[:3,:3];local[j]=np.linalg.inv(base)@w
    def hit(dt):
        q=source['spell1']
        keys=[(-.50,q[1]),(-.24,q[2]),(-.105,q[3]),(0,q[5]),(.055,q[5]),(.19,q[6]),(.34,q[8]),(.48,q[7])]
        for (a,A),(b,B) in zip(keys,keys[1:]):
            if dt<=b:return mix(A,B,ease((dt-a)/(b-a)))
        return keys[-1][1]
    def fight(t):
        j=np.searchsorted(BLINKS,round(t*30),side='right')-1
        if j<0:return sample(source['idle'],min(t*30,17))
        return placed(hit(t-CUTS[j]),angles[j],positions[j])
    seat_turn=yaw(.16)
    seat_ref=world(source['joke_start'][20:30],g.parents)[:,pel,:3,3].mean(0)
    native=world(source['idle'][0],g.parents)
    base_dir=unit(native[ix['Buffbone_Scissors_A_Tip'],:3,3]-native[sc,:3,3])
    dest=unit((.64,-.76,.03))
    parked=native[sc].copy()
    parked[:3,:3]=rot(np.cross(base_dir,dest),np.arccos(np.clip(base_dir@dest,-1,1)))@native[sc,:3,:3]*.54
    parked[:3,3]=[105,61,-64]
    def sit(k):
        src=sample(source['joke_start'],joke_frame(k))
        hip=world_joint(src,g.parents,pel)[:3,3]
        offset=SIT-seat_turn@seat_ref
        # Preserve the sideways weight shift and part of the source's vertical scissor bounce.
        offset[1]-=.65*(hip[1]-seat_ref[1])
        m=placed(src,.16,offset)
        m[sc]=parked;m[ix['Scissors_B']]=source['idle'][0,ix['Scissors_B']]
        return m
    frames=[]
    for k in range(241):
        t=k/30;L=rest.copy()
        L[:141]=fight(t) if k<SEAT_BLINK else sit(k)
        if 124<=k<SEAT_BLINK:
            look=ease((k-124)/13)
            turn(L,ix['Chest'],[0,1,0],.11*look)
            turn(L,ix['Head'],[0,1,0],.24*look)
        # Both doll rigs stay attached to the same seated transform. Pose their
        # own limbs independently for the wave and the quiet head tilt.
        dr=ix['Doll_Root'];dm=ix['Doll_Main']
        L[dr]=trs((SIT[0],CUP_H-7,49),yaw(-.13),1.78)@rest[dr];L[dm]=rest[dm]
        for j in range(109,118):L[j]=rest[j]
        v=np.clip((t-6.5)/1.5,0,1)
        for who in (22,33):
            for side in ('L','R'):
                turn(L,ix[f'P{who}_{side}_Doll_Hip'],[1,0,0],-1.06)
                turn(L,ix[f'P{who}_{side}_Doll_Knee'],[1,0,0],.50)
        wave=np.sin(4*pi*v)*np.sin(pi*v)**.32
        turn(L,ix['P22_L_Doll_Shoulder'],[0,0,1],-.45-.40*wave)
        turn(L,ix['P22_L_Doll_Elbow'],[0,0,1],-.48-.61*wave)
        turn(L,ix['P22_Doll_Head'],[0,0,1],.12*np.sin(2*pi*v))
        turn(L,ix['P33_Doll_Head'],[0,0,1],.20*ease(v/.5))
        turn(L,ix['P33_Doll_Head'],[0,1,0],-.24*ease(v/.6))
        L[ix['RC_Stage']]=np.eye(4)
        cap=ease((k-122)/(SEAT_BLINK-123))
        L[ix['RC_Cup']]=trs((0,0,0),yaw((1-cap)*-.48),max(.0001,cap))
        at_seat=k<SWAP-10
        peak=SEAT_BLINK+2 if at_seat else SWAP
        fade=ease((k-(peak-4))/4)*(1-ease((k-peak)/4))
        L[ix['RC_Change']]=trs((SIT[0],CUP_H+(5 if at_seat else 31),52 if at_seat else 62),rot([1,0,0],-.55),max(.0001,fade*(.52 if at_seat else 1)))
        for j,a in enumerate(ANCHORS):
            d=inward(a);side=unit(np.cross([0,1,0],d));cut=CUTS[j]
            L[ix['RC_Badge'+str(j)]]=trs(LOGOS[j])
            reveal=1.
            age=max(0,t-cut);fall=ease(age/.54)
            for h in (0,1):
                # Retract the outer torn stub; release the inner cloth with a turn and a drop.
                pos=a.copy();stretch=max(.001,reveal)
                spin=.06*np.sin(15*t+j)*reveal
                if h:
                    pos+=d*(14*fall)+side*(12*fall);pos[1]-=32*fall
                    spin+=(-1)**j*1.24*fall
                    stretch*=1-ease((age-.21)/.37)
                else:stretch*=1-ease(age/.38)
                L[ix['RC_Tail'+str(j)+str(h)]]=trs(pos,rot(d,spin),max(.001,stretch))
            silk=ease(age/.24)*(1-ease((t-4.70)/.58))
            origin=a+d*LENGTH*.55+np.array([0,-24,0])
            axis=unit(np.cross(-origin,[0,1,0]))
            L[ix['RC_Silk'+str(j)]]=trs(origin,rot(axis,-.27*(1-cap)),max(.0001,silk))
            pulse=ease((t-cut+.045)/.065)*(1-ease((t-cut-.06)/.23))
            L[ix['RC_Burst'+str(j)]]=trs(origin,yaw(.5*(t-cut)),max(.0001,pulse))
            blink=SEAT_BLINK if j==3 and k>BLINKS[3]+12 else BLINKS[j]
            departure=fight((blink-2)/30)
            oldPos=world_joint(departure,g.parents,pel)[:3,3].copy()
            feet=[world_joint(departure,g.parents,ix[side+'_Foot'])[:3,3] for side in ('L','R')]
            oldPos[[0,2]]=np.mean(feet,axis=0)[[0,2]]
            oldPos[1]=min(p[1] for p in feet)+15
            vis=ease((k-blink+5)/4)*(1-ease((k-blink)/7))
            L[ix['RC_Dash'+str(j)]]=trs(oldPos,rot([1,0,0],-.55),max(.0001,vis))
        frames.append(L)
    np.savez_compressed(WORK/'recall.npz',names=names,parents=parents,bind=bind,inf=inf,local=np.array(frames,dtype='f'),
        prop_pos=np.array(props.p,'f'),prop_uv=np.array(props.uv,'f'),prop_norm=np.array(props.n,'f'),prop_joint=[ix['RC_'+n] for n in props.j],
        prop_tri=np.array(props.f,'u2'),cuts=CUTS,anchors=ANCHORS)
    print('Eight seconds',len(frames),len(names),'joints,',len(props.f),'prop triangles',flush=True)
if __name__=='__main__':choreograph()

