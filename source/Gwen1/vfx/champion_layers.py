"""Shared world-space particle parameters for the native BIN and the offline review."""
from dataclasses import dataclass
from math import cos, sin, tau


@dataclass(frozen=True)
class Sprite:
    name: str
    texture: str
    origin: tuple
    speed: tuple
    size: tuple
    delay: float
    life: float
    rotation: float = 0.
    spin: float = 0.
    rate: float = 0.
    glow: bool = True


SEAL = Sprite('BLG_W_PearlWordmark','w_blg_wordmark',(69,18,218),(0,0,0),
              (318,159),.12,9,glow=False)
CURRENT_SPEEDS = {'ice':-.31, 'rose':.24}
CUP_HALF_SIZE = (181,144)
CUP_YAW = 16.7
CUP_ALPHA = .79


def w_motes():
    for i in range(15):
        a = tau*i/15
        radius = (335,220,370,267,303)[i%5]
        color = ('ice','gold','rose','ice','gold','rose','gold')[i%7]
        speed = 77 if i%2 else -71
        size = (34,24,43,28,32)[i%5]
        yield Sprite(f'BLG_W_LoomSpark_{i:02}',f'blg_crystal_{color}',
                     (cos(a)*radius,12+6*(i%3),sin(a)*radius),
                     (-sin(a)*speed,74+(i%4)*13,cos(a)*speed),
                     (size,size),.10 + (i*7%16)/30,1.03+(i%4)*.11,
                     i*23-65,43 if i%2 else -46,1.28+(i%3)*.17)


def q_shards(stage):
    final = stage == 'Finisher'
    count = 16 if final else 7
    center = (30,92,340) if final else (0,100,287)
    for side, shade in enumerate(('ice','rose')):
        direction = 1 if side else -1
        width = 334 if final else 186
        yield Sprite(f'BLG_Q_{stage}_Silk_{shade}',f'q_silk_{shade}',center,
                     (direction*(65 if final else 43),15,18),(width,width*.40),
                     (.135 if final else .105)+side*.037,.32 if final else .21,
                     direction*(33 if final else 25),direction*27)
    for i in range(count):
        angle = tau*i/count+(.12 if final else .38)
        color = ('ice','gold','rose','ice','rose')[i%5]
        power = ((285,407,326,470) if final else (192,249,225,262))[i%4]
        size = ((47,28,51,35) if final else (33,20,28,30))[i%4]
        yield Sprite(f'BLG_Q_{stage}_Facet_{i:02}',f'blg_crystal_{color}',center,
                     (cos(angle)*power,40+(i%4)*40,sin(angle)*power*.53+52),
                     (size,size),(.15 if final else .12)+(i%3)*.018,
                     (.42 if final else .31)+(i%4)*.03,70-i*33,(-1)**i*(100+(i%3)*35))


def _vals(numbers):
    return ', '.join(f'{v:.6g}' for v in numbers)


def native_sprite(sprite):
    repeated = sprite.rate > 0
    seal = sprite == SEAL
    lifetime = 7 if repeated else sprite.delay+sprite.life+.02
    scale = (*sprite.size,0)
    born = '0, .026, .97, 1' if seal else '0, .10, .63, 1'
    single = '' if repeated else '                isSingleParticle: flag = true\n'
    unfold = ''
    if '_Silk_' in sprite.name:
        unfold = '''                scale0: embed = ValueVector3 {
                    dynamics: pointer = VfxAnimatedVector3fVariableData {
                        times: list[f32] = { 0, 0.22, 0.65, 1 }
                        values: list[vec3] = {
                            { 0.18, 0.5, 1 }
                            { 0.84, 1.25, 1 }
                            { 1, 0.9, 1 }
                            { 1.13, 0.12, 1 }
                        }
                    }
                }
'''
    return f'''            VfxEmitterDefinitionData {{
                emitterName: string = "{sprite.name}"
                timeBeforeFirstEmission: f32 = {sprite.delay:.6g}
                rate: embed = ValueFloat {{ constantValue: f32 = {sprite.rate or 1:.6g} }}
                lifetime: option[f32] = {{ {lifetime:.6g} }}
                particleLifetime: embed = ValueFloat {{ constantValue: f32 = {sprite.life:.6g} }}
{single}                bindWeight: embed = ValueFloat {{ constantValue: f32 = 1 }}
                EmitterPosition: embed = ValueVector3 {{ constantValue: vec3 = {{ {_vals(sprite.origin)} }} }}
                birthVelocity: embed = ValueVector3 {{ constantValue: vec3 = {{ {_vals(sprite.speed)} }} }}
                birthScale0: embed = ValueVector3 {{ constantValue: vec3 = {{ {_vals(scale)} }} }}
{unfold}                isRotationEnabled: flag = true
                birthRotation0: embed = ValueVector3 {{ constantValue: vec3 = {{ {sprite.rotation}, 0, 0 }} }}
                birthRotationalVelocity0: embed = ValueVector3 {{ constantValue: vec3 = {{ {sprite.spin}, 0, 0 }} }}
                isLocalOrientation: flag = false
                blendMode: u8 = {4 if sprite.glow else 1}
                Color: embed = ValueColor {{
                    dynamics: pointer = VfxAnimatedColorVariableData {{
                        times: list[f32] = {{ {born} }}
                        values: list[vec4] = {{
                            {{ 1, 1, 1, 0 }}
                            {{ 1, 1, 1, 1 }}
                            {{ 1, 1, 1, {1 if seal else .85} }}
                            {{ 1, 1, 1, 0 }}
                        }}
                    }}
                }}
                pass: i16 = {32 if seal else 56}
                alphaRef: u8 = 0
                texture: string = "assets/characters/gwen/skins/base/particles/blg_qw/{sprite.texture}.tex"
            }}'''
