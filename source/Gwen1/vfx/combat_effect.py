"""Gwen's native dash, weapon enchantment, attack trails and target-hit callbacks."""
import re
from champion_layers import Sprite, native_sprite
from q_effect import _entries, _matching_brace, fnv1a
from w_effect import ASSET_ROOT, _edit_emitter, _replace_field

SYSTEMS = {f'Gwen_Base_{name}' for name in (
    'E_DashVisual','E_ATKSPD_Buff','E_ATK_Swing','E_Weapon_Trail_Tip01',
    'E_Impact01','E_End_Buff_Cast','BA_Impact01','BA_Impact02','BA_Impact03')}
WAKE = 'Gwen_BLG_E_BodyWake'
WAKE_PATH = 'Characters/Gwen/Skins/Skin0/Particles/'+WAKE
DASH_NODE = 0xe7d2395f
BODY = ((-24,116,-33,39,.245),(19,78,-40,46,.285),(-15,39,-28,31,.215))
BODY_TEXTURE = 'e_body_wake'
BODY_EMIT = .28
GLINTS = ((-.6,45,'ice',26,.17,1.72),(.9,101,'rose',34,.22,1.41),
          (-.8,155,'ice',28,.20,1.83),(.5,125,'rose',17,.14,2.13))


def impact(enhanced, variant=1):
    # An asymmetric constellation opens away from a bright, stationary contact.
    layout = [(0,0,0,0,0,66,0,.25),(-13,8,-91,65,-8,43,.014,.30),
              (15,2,109,44,12,48,.024,.29),(8,-9,60,-75,9,30,.038,.25),
              (-6,13,-32,97,-18,26,.048,.28),(4,15,128,-31,14,20,.064,.23)] if enhanced else [
                  (0,0,0,0,0,49,0,.19),(10,4,70,44,8,33,.012,.24),
                  (-8,-4,-42,-31,4,25,.023,.21),(15,10,109,-70,-8,19,.035,.18),
                  (-13,12,-103,65,15,17,.044,.20)]
    sign=-1 if variant==2 else 1
    for i,(x,y,dx,dy,dz,size,delay,life) in enumerate(layout):
        shade=('ice','rose')[(i+(variant==2))%2]
        yield Sprite(f'BLG_{"E" if enhanced else "BA"+str(variant)}_Hit_{i}',
                     'combat_star_'+shade,(sign*x, (97 if enhanced else 100)+y,0),
                     (sign*dx,dy,dz),(size,size*(1.08 if i==0 else 1)),delay,life,
                     (7+11*i+13*(variant-1))*sign,(-1)**i*(42 if enhanced else 25))


def glints():
    for i,(lateral,z,shade,size,life,rate) in enumerate(GLINTS):
        yield Sprite(f'BLG_E_BladeGlint_{i}','combat_star_'+shade,(lateral,1,z),(0,0,0),
                     (size,size),.05+.095*i,life,9+13*i,(-1)**i*60,rate)


def field(block,name,value):
    if re.search(r'^                '+re.escape(name)+':',block,re.M):
        return _replace_field(block,name,value)
    return block.replace('{','{\n                '+name+': '+value,1)


def value(num):
    return f'embed = ValueFloat {{ constantValue: f32 = {num} }}'


def vec(*items):
    n=len(items)
    return f'embed = ValueVector{n} {{ constantValue: vec{n} = {{ '+', '.join(map(str,items))+' } }'


def fade(peak):
    alphas=(peak*.65,peak,peak*.82,0)
    rows='\n'.join(f'                            {{ 1, 1, 1, {a:.5g} }}' for a in alphas)
    return f'''embed = ValueColor {{
                    dynamics: pointer = VfxAnimatedColorVariableData {{
                        times: list[f32] = {{ 0, 0.10, 0.53, 1 }}
                        values: list[vec4] = {{
{rows}
                        }}
                    }}
                }}'''


def dims(block,width):
    return field(block,'birthScale0',vec(width,9,9))


def short_trail(stem,origin,width,life,emit,name):
    return f'''            VfxEmitterDefinitionData {{
                emitterName: string = "{name}"
                rate: embed = ValueFloat {{ constantValue: f32 = 90 }}
                particleLifetime: {value(life)}
                lifetime: option[f32] = {{ {emit} }}
                EmitterPosition: {vec(*origin)}
                birthScale0: {vec(width,9,9)}
                Color: {fade(.94)}
                primitive: pointer = VfxPrimitiveCameraTrail {{
                    mTrail: embed = VfxTrailDefinitionData {{
                        mMode: u8 = 1
                        mCutoff: f32 = 400
                        mBirthTilingSize: {vec(115,0,0)}
                        mSmoothingMode: u8 = 1
                    }}
                }}
                isUniformScale: flag = true
                blendMode: u8 = 4
                pass: i16 = 28
                texture: string = "{ASSET_ROOT}{stem}.tex"
            }}'''


def overlay(e,stem,opacity):
    e=_edit_emitter(e,stem)
    # Stock colour lookup multiplies the authored fibres by Gwen's base palette.
    match=re.search(r'^                textureMult: [^\n]+\{',e,re.M)
    if match:
        end=_matching_brace(e,match.end()-1)
        e=e[:match.start()]+e[end+1:]
    return field(field(e,'Color',fade(opacity)),'blendMode','u8 = 4')


def extra_glint(spec):
    e=field(native_sprite(spec),'particleIsLocalOrientation','flag = true')
    return re.sub(r'^                lifetime:.*\n','',e,flags=re.M)


def edit_emitter(system,name,e):
    if system.endswith('DashVisual'):
        if name=='LongGeo_Strands':
            return overlay(e,'e_dash_filament',.73)
        if name.startswith('Sparkles'):
            return field(overlay(e,'combat_star_'+('rose' if name.endswith('1') else 'ice'),.68),'texDiv','vec2 = { 1, 1 }')
    elif system.endswith('End_Buff_Cast') and name.startswith('Wall_Strings'):
        return overlay(e,'e_dash_filament',.57)
    elif system.endswith('ATK_Swing'):
        return overlay(e,'e_swing_brocade' if name=='Add_Linger' else 'e_dash_filament',.96 if name=='Add_Linger' else .84)
    elif system.endswith('ATKSPD_Buff'):
        if name=='Weapon_Avatar_Glow1':
            # This is the real attached-mesh pass (Scissors submesh), not the
            # two old oversized arbitrary-quad glow planes in this buff.
            e=overlay(e,'e_blade_facets',.94)
            e=field(e,'timeBeforeFirstEmission','f32 = 0.025')
            e=field(e,'rate',value(2.2))
            e=field(e,'particleLifetime',value(1.7))
            e=field(e,'birthColor','embed = ValueColor { constantValue: vec4 = { 1, 1, 1, 0.8 } }')
            e=field(e,'pass','i16 = 30')
            return field(e,'birthUvScrollRate',vec(0,0))
        if name.startswith('Smokey Trail'):
            e=overlay(e,'e_dash_filament',.59)
            e=field(e,'birthVelocity',vec(-148,14,0))
            return dims(field(e,'particleLifetime',value(.19)),21)
        if name=='Front':
            e=_edit_emitter(e,'e_blade_facets')
            return field(e,'birthUvScrollRate',vec(.38,.075))
        if name=='FlameMesh4':
            return overlay(e,'e_dash_filament',.50)
        if name=='Sharp_Edge_Bright1':
            # The stock emitter is a ground-facing arbitrary quad; it reads as
            # a floating color block in the game camera. Weapon shine is now
            # carried by the attached Scissors surface above.
            return None
        if name.startswith('Bloom_Impact'):
            return overlay(e,'combat_star_rose',.8)
    return e


def with_emitters(block,fn):
    marker='complexEmitterDefinitionData: list[pointer] = {'
    start=block.index(marker)+len(marker)
    end=_matching_brace(block,start-1)-1
    body=block[start:end]
    emitters=[]
    for m in re.finditer(r'^            VfxEmitterDefinitionData \{',body,re.M):
        e=body[m.start():_matching_brace(body,m.end()-1)]
        name=re.search(r'emitterName: string = "([^"]+)"',e)[1].strip()
        emitters.append((name,e))
    assert emitters
    return block[:start]+'\n'+'\n'.join(fn(emitters))+'\n        '+block[end:]


def edit_system(system,block):
    if '_Impact' in system:
        specs=impact('_E_' in system,int(system[-2:]))
        return with_emitters(block,lambda _: [field(native_sprite(s),'FlexShapeDefinition',
            'embed = VfxFlexShapeDefinitionData { scaleEmitOffsetByBoundObjectSize: f32 = 0.005 }') for s in specs])
    if system.endswith('Weapon_Trail_Tip01'):
        return with_emitters(block,lambda _: [
            short_trail('e_swing_brocade',(0,0,0),39,.21,.34,'BLG_E_EdgeBrocade'),
            short_trail('e_dash_filament',(0,0,-23),14,.25,.34,'BLG_E_InnerHem')])
    def edit(emitters):
        result=[patched for name,e in emitters
                if (name!='Front' or not system.endswith('ATKSPD_Buff'))
                and not (system.endswith('ATKSPD_Buff') and name.startswith('BLG_E_BladeGlint_'))
                and not (system.endswith('ATKSPD_Buff') and name=='BLG_E_BladeSweep')
                for patched in [edit_emitter(system,name,e)] if patched is not None]
        if system.endswith('ATKSPD_Buff'):
            weapon=next(e for e in result if re.search(r'emitterName: string = "Weapon_Avatar_Glow1"',e))
            sweep=overlay(weapon,'e_blade_sweep',.86)
            sweep=field(sweep,'emitterName','string = "BLG_E_BladeSweep"')
            sweep=field(sweep,'timeBeforeFirstEmission','f32 = 0.035')
            sweep=field(sweep,'rate',value(3.1))
            sweep=field(sweep,'particleLifetime',value(1.05))
            sweep=field(sweep,'birthColor','embed = ValueColor { constantValue: vec4 = { 1, 1, 1, 0.76 } }')
            sweep=field(sweep,'birthUvScrollRate',vec(.32,-.11))
            sweep=field(sweep,'pass','i16 = 31')
            result.append(sweep)
            result.extend(extra_glint(s) for s in glints())
        return result
    return with_emitters(block,edit)


def apply(skin,anim):
    prefix,records,suffix=_entries(skin)
    wake_key=fnv1a(WAKE_PATH)
    alias=fnv1a(WAKE)
    assert wake_key not in {k for k,_,_ in records}
    out=[]; changed=set()
    for _,kind,block in records:
        if kind=='ResourceResolver':
            marker='resourceMap: map[hash, link] = {'
            assert f'0x{alias:08x}' not in block and block.count(marker)==1
            block=block.replace(marker,marker+f'\n            0x{alias:08x} = 0x{wake_key:08x}')
        elif kind=='VfxSystemDefinitionData':
            match=re.search(r'particleName: string = "([^"]+)"',block)
            if match and match[1] in SYSTEMS:
                revised=edit_system(match[1],block)
                assert revised!=block
                block=revised
                changed.add(match[1])
        out.append(block)
    assert changed==SYSTEMS
    trails='\n'.join(short_trail(BODY_TEXTURE,(x,y,z),w,life,BODY_EMIT,f'BLG_Dash_Thread_{i}')
                     for i,(x,y,z,w,life) in enumerate(BODY))
    out.append(f'''    0x{wake_key:08x} = VfxSystemDefinitionData {{
        complexEmitterDefinitionData: list[pointer] = {{
{trails}
        }}
        visibilityRadius: f32 = 400
        particleName: string = "{WAKE}"
        particlePath: string = "{WAKE_PATH}"
        objectPath: hash = 0x{wake_key:08x}
    }}''')
    marker=f'0x{DASH_NODE:08x} = AtomicClipData {{'
    assert anim.count(marker)==1
    event=f'''
                mEventDataMap: map[hash, pointer] = {{
                    0x{fnv1a(WAKE+'_event'):08x} = ParticleEventData {{
                        mEffectKey: hash = 0x{alias:08x}
                        mParticleEventDataPairList: list[embed] = {{
                            ParticleEventDataPair {{ mBoneName: hash = 0x{fnv1a('Buffbone_Glb_Ground_Loc'):08x} }}
                        }}
                        mScalePlaySpeedWithAnimation: bool = true
                    }}
                }}'''
    return prefix+'\n'+'\n'.join(out)+'\n'+suffix,anim.replace(marker,marker+event)
