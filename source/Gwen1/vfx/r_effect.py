"""Needlework visuals bound to Skin0's existing casts, missiles and recast buffs."""
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from champion_layers import Sprite, native_sprite
from combat_effect import fade, field, overlay, short_trail, value, vec, with_emitters
from q_effect import _entries, _matching_brace, fnv1a
from w_effect import ASSET_ROOT
from r_mesh import DRAW_STEPS, MESH_ROOT

PREFIX='Gwen_Base_R_'
SYSTEMS={PREFIX+s for s in ('Cast01','Cast02','Cast03','Hand_Trail01','Missile','Missile02',
       'BonusNeedles_Buff02','BonusNeedles02_Buff02','BonusNeedles_Child')}
CHILD='BonusNeedles_Child'
CHILD_ALIAS={'ice':0x2e82aa72, **{s:fnv1a('Gwen_BLG_R_Hover_'+s) for s in ('rose','crown')}}
STYLES={1:'silver',2:'loom',3:'crown'}
ORBIT_NAME='Gwen_BLG_R_SpoolOrbit'
ORBIT_NODES={0xed046bdf,0xb7f64047}
# delay, start angle, degrees per second, initial height, climb speed, mesh scale, texture
ORBIT_LIFE=.64
ORBIT=((0.,-145,610,-48,143,1.,'silver'),(.055,37,563,-16,129,.91,'loom'))

# emitter, local right/up/forward, activation in seconds, needle finish
HOVER={
    2:(('Needle_Birth7',(-105,122,-34),.055,'ice'),
       ('Needle_Birth8',(0,165,-81),.15,'rose'),
       ('Needle_Birth4',(105,122,-34),.245,'ice')),
    3:(('Needle_Birth8',(0,233,-80),.035,'crown'),
       ('Needle_Birth7',(-72,194,-74),.105,'rose'),
       ('Needle_Birth4',(72,194,-74),.105,'ice'),
       ('Needle_Birth10',(-143,151,-65),.185,'ice'),
       ('Needle_Birth9',(143,151,-65),.185,'rose'))}


FACET_RATE=-.83
HOLD_FLOW_PERIOD=2.
HOLD_FLOW_LIFE=2.16
ORBIT_HAZE=(('ice',.53,-.70),('rose',.45,-.54))
GRAIN_LAG=16
GRAIN_DRIFT=.92
MIST_RELEASE_TIMES=(0,.18,.43,.72,1)
MIST_RELEASE_ALPHA=(1,.88,.48,.12,0)
VEIL_RELEASE=.07
SILK_RELEASE=.082


@dataclass(frozen=True)
class MistTrail:
    shade: str
    lateral: float
    width: float
    life: float
    tile: float
    scroll: float
    opacity: float


def mist_trails(final):
    # Longer overlapping samples keep the flight ribbon connected at gameplay
    # camera scale. The rose pass sits inside the blue edge so the colors read
    # as a designed pair rather than two separated dashes.
    return (MistTrail('ice',-6,94,.31 if final else .34,250,-.58,.78 if final else .88),
            MistTrail('rose',6,73,.275 if final else .30,225,-.72,.69 if final else .79))


def flight_splinters(crown):
    for i,(tint,x,y,delay) in enumerate((('rose',16,5,.012),('gold' if crown else 'ice',-11,-8,.066))):
        yield Sprite('BLG_EyeSplinter'+str(i),'blg_crystal_'+tint,(x,y,-42),
                     (2.6*x,17+i*13,-19),(13+i*4,17+i*4),delay,.21,28+i*39,(-1)**i*120)


def splinter_emitter(s):
    e=native_sprite(s)
    base=(0,-170,25)
    e=field(e,'EmitterPosition',vec(*(b+p for b,p in zip(base,s.origin))))
    e=field(e,'bindWeight',value(.04))
    e=field(e,'Color',fade(.85))
    return field(e,'pass','i16 = 58')


def mist_release(e,seconds):
    times=', '.join(map(str,MIST_RELEASE_TIMES))
    rows='\n'.join(f'                            {{ 1, 1, 1, {a} }}' for a in MIST_RELEASE_ALPHA)
    linger=f'''pointer = VfxLingerDefinitionData {{
                    UseSeparateLingerColor: flag = true
                    SeparateLingerColor: embed = ValueColor {{
                        dynamics: pointer = VfxAnimatedColorVariableData {{
                            times: list[f32] = {{ {times} }}
                            values: list[vec4] = {{
{rows}
                            }}
                        }}
                    }}
                }}'''
    return field(field(e,'particleLinger',f'option[f32] = {{ {seconds} }}'),'Linger',linger)


def veil_color(peak,times):
    t=', '.join(map(str,times))
    alphas=(0,peak,peak,0)
    rows='\n'.join(f'{{ 1, 1, 1, {a} }}' for a in alphas)
    return ('embed = ValueColor {\n                    dynamics: pointer = VfxAnimatedColorVariableData {\n'
            +'                        times: list[f32] = { '+t+' }\n                        values: list[vec4] = {\n'
            +rows+'\n                        }\n                    }\n                }')


def veil_strength(shade,hover):
    return .64 if hover else (.42 if shade=='crown' else .53)


def needle_veil(e,shade,hover):
    tint='rose' if shade=='rose' else 'ice'
    e=mesh_pass(e,'BLG_R_EyeVeil','r_needle_veil','r_flow_'+tint)
    # Inherit the native needle pose. Use the default wrapping sampler for the flow.
    e=re.sub(r'^                texAddressModeBase: u8 = [^\n]+\n','',e,flags=re.M)
    peak=veil_strength(shade,hover)
    times=(0,.072,.926,1) if hover else (0,.025,.95,1)
    for key,v in [('blendMode','u8 = 1'),('pass','i16 = 21'),('uvScrollClamp','flag = false'),
                  ('birthUvScrollRate',vec(-1/HOLD_FLOW_PERIOD,0)),('Color',veil_color(peak,times))]:
        e=field(e,key,v)
    if hover:
        e=field(e,'timeBeforeFirstEmission','f32 = 0')
        e=field(e,'rate',value(1/HOLD_FLOW_PERIOD))
        e=field(e,'particleLifetime',value(HOLD_FLOW_LIFE))
    else:
        e=mist_release(e,VEIL_RELEASE)
    return e


def cast_sparks(stage):
    for i in range((2,3,5)[stage-1]):
        x=(-1)**i*(16+9*i)
        shade=('ice','rose','gold')[min(stage-1,i%3)]
        yield Sprite(f'BLG_R{stage}_EyeletSpark_{i}','blg_crystal_'+shade,
                     (x,107+i%2*16,21),(x*1.4,24+i*7,49+i*9),
                     (20+i%3*5,22+i%3*5),.13+.023*i,.20+.025*(i%2),12*i,35*(-1)**i)


def mesh_path(e,mesh):
    e,n=re.subn(r'(mSimpleMeshName: string = ")[^"]+(")',lambda m:m[1]+MESH_ROOT+mesh+'.scb'+m[2],e)
    assert n==1
    return field(e,'disableBackfaceCull','flag = true')


def needle(e,shade,alpha=1):
    e=overlay(e,'r_needle_'+shade,alpha)
    for k,v in [('birthUVOffset',vec(0,0)),('birthUvScrollRate',vec(0,0)),('uvScale',vec(1,1)),
                ('particleUVScrollRate','embed = IntegratedValueVector2 { constantValue: vec2 = { 0, 0 } }'),
                ('texDiv','vec2 = { 1, 1 }'),('blendMode','u8 = 1')]:
        e=field(e,k,v)
    return mesh_path(e,'r_crystal_needle')


def mesh_pass(e,name,mesh,texture):
    e=mesh_path(e,mesh)
    e=field(e,'emitterName',f'string = "{name}"')
    return field(e,'texture',f'string = "{ASSET_ROOT}{texture}.tex"')


def launch_pass(e,name,mesh,texture,delay,life):
    e=mesh_pass(e,name,mesh,texture)
    e=field(e,'timeBeforeFirstEmission',f'f32 = {delay}')
    e=field(e,'particleLifetime',value(life))
    return field(e,'blendMode','u8 = 4')


def hover_child(block,shade):
    def edit(emitters):
        out=[]
        for name,e in emitters:
            if name in ('Needle_Birth','Needle_Hold'):
                e=needle(e,shade)
                e=field(e,'birthScale0',vec(.66,.72,.72))
                if name=='Needle_Hold':
                    e=field(e,'timeBeforeFirstEmission','f32 = 0.28')
                    out.append(needle_veil(e,shade,True))
                    gleam=mesh_pass(e,'BLG_HeldFacetLight','r_crystal_needle','r_facet_light')
                    for k,v in [('blendMode','u8 = 4'),('birthUvScrollRate',vec(FACET_RATE,0)),
                                ('uvScrollClamp','flag = false'),('Color',fade(.72))]:
                        gleam=field(gleam,k,v)
                    out.append(gleam)
                out.append(mesh_pass(e,'BLG_EyeSilk_'+name,'r_slack_'+shade,'r_fibre_'+shade))
            elif name in ('LongGeo_Strands','BaseMist_outer','mists') or name.startswith('Strands_Ribbon'):
                continue
            elif name=='Bloom_Impact 1':
                e=overlay(e,'blg_crystal_'+('gold' if shade=='crown' else shade),.81)
            out.append(e)
        glint=Sprite('BLG_R_HoverSpark_'+shade,'blg_crystal_'+('gold' if shade=='crown' else shade),
                     (0,0,-75),(0,0,0),(27,30),.07,.22,8,40,1.30)
        out.append(field(native_sprite(glint),'particleIsLocalOrientation','flag = true'))
        return out
    return with_emitters(block,edit)


def edit_holders(block,stage):
    holders={n:(offset,delay,shade) for n,offset,delay,shade in HOVER[stage]}
    def edit(emitters):
        out=[]
        found=set()
        for name,e in emitters:
            if name in holders:
                pos,delay,shade=holders[name]
                found.add(name)
                assert e.count('effectKey: hash = 0x2e82aa72')==1
                e=e.replace('effectKey: hash = 0x2e82aa72',f'effectKey: hash = 0x{CHILD_ALIAS[shade]:08x}')
                e=field(e,'timeBeforeFirstEmission',f'f32 = {delay}')
                e=field(e,'SpawnShape','pointer = 0xee39916f { emitOffset: vec3 = { '+', '.join(map(str,pos))+' } }')
                e=field(e,'velocity',vec(0,0,0))
                e=field(e,'birthRotation0',vec(90,0,round(-pos[0]*.17,2)))
                e=field(e,'rotation0','embed = IntegratedValueVector3 { constantValue: vec3 = { 0, 0, 0 } }')
            elif name in ('Open4','Single_White_Strand','mesh_Q_spikes1'):
                continue
            out.append(e)
        assert found==set(holders)
        return out
    return with_emitters(block,edit)


def cast(block,stage):
    def edit(emitters):
        out=[]
        for name,e in emitters:
            if name.startswith(('Main_Lead','Strings_Supp','Mesh','drak_trail')):
                continue
            elif name.startswith('Avatar_Glow'):
                e=overlay(e,'e_blade_facets',.30)
            out.append(e)
        return out+[native_sprite(s) for s in cast_sparks(stage)]
    return with_emitters(block,edit)


def flight_wake(face, final):
    # Use the needle's single, fully bound mesh emitter. Each missile carries
    # one unbroken UV island per veil for its entire flight, in every direction.
    e = mesh_pass(face, 'BLG_R_FlightWake', 'r_flight_wake', 'r_flight_wake')
    grow = '''embed = ValueVector3 {
                    dynamics: pointer = VfxAnimatedVector3fVariableData {
                        times: list[f32] = { 0, 0.08, 0.19, 0.28, 1 }
                        values: list[vec3] = {
                            { 0.60, 0.60, 0.10 }
                            { 0.80, 0.80, 0.38 }
                            { 0.96, 0.96, 0.77 }
                            { 1, 1, 1 }
                            { 1, 1, 1 }
                        }
                    }
                }'''
    width = 1.10 if final else 1.42
    e = field(e, 'birthScale0', vec(width,width,.86 if final else 1.0))
    e = field(e, 'scale0', grow)
    e = field(e, 'pass', 'i16 = 20')
    e = field(e, 'Color', veil_color(.88 if final else .98, (0,.028,.92,1)))
    return mist_release(e,.15)


@lru_cache(maxsize=2)
def native_flight_layers(final):
    stock = Path(__file__).resolve().parent.parent/'rig-study/skin0_named.rito'
    _, records, _ = _entries(stock.read_text(encoding='utf-8'))
    name = PREFIX + ('Missile02' if final else 'Missile')
    system, = [b for _,_,b in records if f'particleName: string = "{name}"' in b]
    layers = []
    for m in re.finditer(r'^            VfxEmitterDefinitionData \{',system,re.M):
        e = system[m.start():_matching_brace(system,m.end()-1)]
        tag = re.search(r'emitterName: string = "([^"]+)"',e)[1]
        if tag not in ('HoneyTrail','HoneyTrail1','Bloom_Over'):
            continue
        # Keep the original trail's spawn offset and render primitive. No transparent
        # U ends on the repeated texture: only particle age feathers the tail.
        for attr in ('alphaErosionDefinition','textureMult'):
            entry = re.search(r'^                '+attr+r': [^\n]+?\{', e, re.M)
            if entry:
                e = e[:entry.start()] + e[_matching_brace(e,entry.end()-1):]
        glow = tag == 'Bloom_Over'
        ice = tag == 'HoneyTrail'
        tint = (.13,.65,1.,.97) if ice else (1.,.17,.58,.94)
        if glow: tint = (.58,.71,1.,.91)
        rgba=', '.join(map(str,tint))
        if glow:
            color=f'embed = ValueColor {{ constantValue: vec4 = {{ {rgba} }} }}'
        else:
            transparent=', '.join(map(str,(*tint[:3],0)))
            color=f'''embed = ValueColor {{
                    constantValue: vec4 = {{ {rgba} }}
                    dynamics: pointer = VfxAnimatedColorVariableData {{
                        times: list[f32] = {{ 0, 0.068, 1 }}
                        values: list[vec4] = {{ {{ {transparent} }} {{ {rgba} }} {{ {rgba} }} }}
                    }}
                }}'''
        e=field(e,'birthColor',color)
        e=field(e,'emitterName','string = "BLG_R_'+('EyeLight' if glow else 'WindBlue' if ice else 'WindRose')+'"')
        e=field(e,'timeBeforeFirstEmission','f32 = 0')
        e=field(e,'importance','u8 = 3')
        e=field(e,'Color',fade(.92))
        if glow:
            e=field(e,'isSingleParticle','flag = true')
            e=field(e,'rate',value(1))
            e=field(e,'bindWeight',value(1))
            e=field(e,'birthVelocity',vec(0,0,0))
            e=field(e,'birthScale0',vec(81,81,1))
            e=field(e,'particleLifetime',value(.90))
            e=field(e,'blendMode','u8 = 4')
        else:
            e=field(e,'texture',f'string = "{ASSET_ROOT}r_wind_fibre.tex"')
            e=field(e,'rate',value(95 if ice else 80))
            e=field(e,'particleLifetime',value(.40 if ice else .30))
            width = (116 if ice else 60) * (.80 if final else 1)
            e=field(e,'birthScale0',vec(width,20,20))
            e=field(e,'texDiv','vec2 = { 1, 1 }')
            e=field(e,'blendMode','u8 = 1' if ice else 'u8 = 4')
            e=field(e,'scale0','''embed = ValueVector3 {
                    dynamics: pointer = VfxAnimatedVector3fVariableData {
                        times: list[f32] = { 0, 0.22, 0.64, 1 }
                        values: list[vec3] = { { 0.65, 1, 1 } { 1, 1, 1 } { 0.69, 1, 1 } { 0.04, 1, 1 } }
                    }
                }''')
            e=mist_release(e,.13)
        layers.append(e)
    assert len(layers)==3, name
    return tuple(layers)


def tip_flash(face,final):
    e=mesh_pass(face,'BLG_R_TipGlint','r_tip_glint','combat_star_rose' if final else 'combat_star_ice')
    e=field(e,'blendMode','u8 = 4')
    e=field(e,'pass','i16 = 1000')
    width=1.05 if final else 1.35
    e=field(e,'birthScale0',vec(width,width,1.19))
    color='''embed = ValueColor {
                    dynamics: pointer = VfxAnimatedColorVariableData {
                        times: list[f32] = { 0, 0.036, 0.17, 0.32, 0.54, 0.74, 1 }
                        values: list[vec4] = { { 1, 1, 1, 0.42 } { 1, 1, 1, 1 } { 1, 1, 1, 0.39 }
                            { 1, 1, 1, 0.88 } { 1, 1, 1, 0.49 } { 1, 1, 1, 0.80 } { 1, 1, 1, 0 } }
                    }
                }'''
    return field(e,'Color',color)


def missile(block,final):
    # One solid enamel surface is enough. The stock effect superimposed four
    # same-geometry colour lookups with different scales.
    face='NEEDLDMESH1' if final else 'NEEDLDMESH'
    def edit(emitters):
        out=[]
        for name,e in emitters:
            # `apply` also polishes the 1.4.2 project seed, which already has
            # an earlier BLG pass. Replace our generated passes in place so
            # applying the polish twice cannot stack transparent meshes.
            if name in ('BLG_R_FlightWake','BLG_R_WindBlue','BLG_R_WindRose','BLG_R_EyeLight','BLG_R_TipGlint',
                        'BLG_R_EyeVeil','BLG_r_pull_loose','BLG_r_pull_half',
                        'BLG_r_pull_taut','BLG_GildFromEye') or name.startswith(
                        ('BLG_R_ConnectedMist_','BLG_EyeSplinter')):
                continue
            if name.startswith('NEEDLDMESH'):
                if name==face:
                    shade='crown' if final else 'ice'
                    face_mesh=field(needle(e,shade),'scale0',vec(1,1,1))
                    face_mesh=field(face_mesh,'birthScale0',vec(1.67,1.63,1.19))
                    # The visible crystal and its coloured slipstream share the main particle.
                    flying=mesh_path(face_mesh,'r_projectile')
                    flying=field(flying,'texture',f'string = "{ASSET_ROOT}r_projectile_{shade}.tex"')
                    out.append(flying)
                    out.append(tip_flash(face_mesh,final))
                    out.append(flight_wake(face_mesh,final))
                    # These passes still use the original, unexpanded mesh coordinates.
                    wide_face=field(face_mesh,'birthScale0',vec(3.34,3.26,1.19))
                    out.append(needle_veil(wide_face,shade,False))
                    for mesh,delay,life in DRAW_STEPS:
                        out.append(launch_pass(face_mesh,'BLG_'+mesh,mesh,'r_fibre_'+shade,delay,life))
                    if final:
                        glow=launch_pass(wide_face,'BLG_GildFromEye','r_crystal_needle','r_gilt_sweep',0,.25)
                        out.append(field(glow,'birthUvScrollRate',vec(-3.65,0)))
                continue
            if name.startswith(('HoneyTrail','Strands_Ribbon','LongGeo_Strands','TrailCenter',
                                'Sparkles','SmallStarTrail','Left','Right','BaseMist','Bloom','Temp_GroundGlow')):
                continue
            out.append(e)
        out.extend(splinter_emitter(s) for s in flight_splinters(final))
        out.extend(native_flight_layers(final))
        return out
    return with_emitters(block,edit)


def orbit_system():
    path='Characters/Gwen/Skins/Skin0/Particles/'+ORBIT_NAME
    parts=[]
    for i,(delay,angle,speed,height,rise,scale,style) in enumerate(ORBIT):
        sprite=Sprite(f'BLG_R_Spool_{i}','r_cast_'+style,(0,height,0),(0,rise,0),
                      (scale,scale),delay,ORBIT_LIFE)
        e=native_sprite(sprite)
        for key,val in [('primitive','pointer = VfxPrimitiveMesh { mMesh: embed = VfxMeshDefinitionData { mSimpleMeshName: string = "'+MESH_ROOT+'r_spiral.scb" } }'),
                        ('birthScale0',vec(scale,scale,scale)),('birthRotation0',vec(0,angle,0)),
                        ('birthRotationalVelocity0',vec(0,speed,0)),('disableBackfaceCull','flag = true'),
                        ('particleIsLocalOrientation','flag = false')]:
            e=field(e,key,val)
        parts.append(e)
        shade,peak,scroll=ORBIT_HAZE[i]
        haze=mesh_pass(e,'BLG_R_OrbitHaze_'+shade,'r_orbit_veil','r_orbit_haze_'+shade)
        for key,val in [('blendMode','u8 = 1'),('pass','i16 = 22'),('birthUvScrollRate',vec(scroll,0)),
                        ('Color',veil_color(peak,(0,.14,.64,1)))]:
            haze=field(haze,key,val)
        parts.append(haze)
        if i==0:
            grains=mesh_pass(e,'BLG_R_DriftingCondensate','r_orbit_grains','r_orbit_pearl')
            for key,val in [('pass','i16 = 31'),('birthRotation0',vec(0,angle-GRAIN_LAG,0)),
                            ('birthRotationalVelocity0',vec(0,round(speed*GRAIN_DRIFT,3),0)),
                            ('Color',veil_color(.73,(0,.20,.64,1)))]:
                grains=field(grains,key,val)
            parts.append(grains)
    block='\n'.join(parts)
    k=fnv1a(path)
    return k,f'''    0x{k:08x} = VfxSystemDefinitionData {{
        complexEmitterDefinitionData: list[pointer] = {{
{block}
        }}
        visibilityRadius: f32 = 450
        particleName: string = "{ORBIT_NAME}"
        particlePath: string = "{path}"
        objectPath: hash = 0x{k:08x}
    }}'''


def bind_orbit(anim):
    event=f'''                    0x{fnv1a(ORBIT_NAME+'_event'):08x} = ParticleEventData {{
                        mEffectKey: hash = 0x{fnv1a(ORBIT_NAME):08x}
                        mParticleEventDataPairList: list[embed] = {{
                            ParticleEventDataPair {{ mBoneName: hash = 0x{fnv1a('Pelvis'):08x} }}
                        }}
                        mScalePlaySpeedWithAnimation: bool = true
                    }}'''
    for k in ORBIT_NODES:
        marker=f'0x{k:x} = ParametricClipData {{'
        assert anim.count(marker)==1
        start=anim.index(marker)
        end=_matching_brace(anim,start+len(marker)-1)
        node=anim[start:end]
        events='mEventDataMap: map[hash, pointer] = {'
        assert node.count(events)==1
        anim=anim[:start]+node.replace(events,events+'\n'+event)+anim[end:]
    return anim


def apply(skin):
    prefix,records,suffix=_entries(skin)
    child=next((k,b) for k,_,b in records if f'particleName: string = "{PREFIX+CHILD}"' in b)
    clones={}
    for shade in ('rose','crown'):
        name='Gwen_BLG_R_Hover_'+shade
        path='Characters/Gwen/Skins/Skin0/Particles/'+name
        key=fnv1a(path)
        assert key not in {k for k,_,_ in records}
        b=hover_child(child[1],shade).replace(PREFIX+CHILD,name)
        b,count=re.subn(rf'\b0x0*{child[0]:x}\b',f'0x{key:08x}',b)
        assert count==2
        clones[shade]=(key,b)
    changed=set()
    out=[]
    orbit_key,orbit=orbit_system()
    assert orbit_key not in {k for k,_,_ in records}
    for k,kind,b in records:
        if kind=='ResourceResolver':
            marker='resourceMap: map[hash, link] = {'
            assert b.count(marker)==1 and all(f'0x{CHILD_ALIAS[s]:08x}' not in b for s in clones)
            b=b.replace(marker,marker+''.join(f'\n            0x{CHILD_ALIAS[s]:08x} = 0x{key:08x}' for s,(key,_) in clones.items()))
            assert f'0x{fnv1a(ORBIT_NAME):08x}' not in b
            b=b.replace(marker,marker+f'\n            0x{fnv1a(ORBIT_NAME):08x} = 0x{orbit_key:08x}')
        match=re.search(r'particleName: string = "([^"]+)"',b)
        if match and match[1] in SYSTEMS:
            name=match[1][len(PREFIX):]
            if name.startswith('Cast'):
                b=cast(b,int(name[-1]))
            elif name.startswith('Missile'):
                b=missile(b,name.endswith('02'))
            elif name==CHILD:
                b=hover_child(b,'ice')
            elif name=='Hand_Trail01':
                b=with_emitters(b,lambda _: [short_trail('r_thread_loom',(0,0,0),22,.17,.49,'BLG_R_HandFloss')])
            else:
                b=edit_holders(b,3 if name.startswith('BonusNeedles02') else 2)
            changed.add(match[1])
        out.append(b)
    assert changed==SYSTEMS
    return prefix+'\n'+'\n'.join(out+[b for _,b in clones.values()]+[orbit])+'\n'+suffix
