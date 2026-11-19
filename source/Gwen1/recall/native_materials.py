"""Bind the skin artwork to compile configurations authored for shipped skinned materials."""
import re
import subprocess
from core import fmt_key
from build_qw import DEFAULT_GAME, ritobin_args
from q_effect import _entries, _matching_brace

ROOT = 'assets/characters/gwen/skins/base/'
HERO = ROOT + 'blg_gwen_detail.tex'
WEAPON = ROOT + 'blg_crystal_shears.tex'
BODY_RMA = ROOT + 'blg_gwen_surface_rma.tex'
WEAPON_RMA = ROOT + 'blg_crystal_shears_rma.tex'
DOLL_RMA = ROOT + 'blg_2233_textile_rma.tex'
DOLL_DIFFUSE = ROOT + 'blg_2233_doll.tex'
DOLL_REFLECTION = ROOT + 'blg_2233_textile_reflection.tex'
DOLL_MATERIAL = fmt_key('Characters/Gwen/Skins/Skin0/Materials/BLG2233Textile')
SHEAR = fmt_key('Characters/Gwen/Skins/Skin0/Materials/BLGCrystalShears')
SOLID_SHADER = '0x12496cde'
BODY_REFLECTION = ROOT + 'blg_gwen_reflection_mask.tex'
WEAPON_REFLECTION = ROOT + 'blg_shears_reflection_mask.tex'
REFLECTION_LIGHT = ROOT + 'blg_studio_reflection.tex'


def installed_bin(path, dest):
    subprocess.run([*ritobin_args(), 'gamedata', 'extract',
                    path, '--game-dir', str(DEFAULT_GAME), '--index-dir',
                    str(dest.parent.parent/'game-data-index'), '-o', str(dest)], check=True)


def material(champion, skin, record, tmp):
    source = tmp / f'{champion}{skin}.rito'
    installed_bin(f'data/characters/{champion}/skins/skin{skin}.bin', source)
    return next(row for key, kind, row in _entries(source.read_text('utf8'))[1]
                if key == record and kind == 'StaticMaterialDef')


def bind_material(template, key, title, samplers, values):
    # A texture or numeric uniform changes the look without creating a shader permutation.
    row = re.sub(r'^    0x[\da-f]+ =', '    ' + key + ' =', template, count=1)
    row = re.sub(r'(name: hash\[u64\] = )0x[\da-f]+', r'\g<1>'+title, row, count=1)
    for name, path in samplers.items():
        value = path if path.startswith('0x') else '"'+path+'"'
        expr = r'(TextureName: string = "' + re.escape(name) + r'"\s+texturePath: file = )0x[\da-f]+'
        row, count = re.subn(expr, r'\g<1>' + value, row)
        if count != 1:raise ValueError(f'Expected one sampler {name} in {key}, found {count}')
    for name, vector in values.items():
        expr = (r'(StaticMaterialShaderParamDef \{\s*name: string = "' + re.escape(name)
                + r'")(?:\s*value: vec4 = \{[^}]*\})?(\s*\})')
        literal = ', '.join(map(str, vector))
        row, count = re.subn(expr, r'\g<1>\n                value: vec4 = { '+literal+r' }\g<2>',row)
        if count != 1:raise ValueError(f'Expected one uniform {name} in {key}, found {count}')
    return row


def remove_field(text, name):
    start = text.find(name+':')
    if start < 0:return text
    end = _matching_brace(text, text.index('{', start))
    return text[:start]+text[end:]


def definitions(stock, tmp):
    title = re.search(r'name: hash\[u64\] = (0x[\da-f]+)', stock)[1]
    # BlendMod=1 selects diffuse + masked reflection. Neither the diffuse alpha
    # nor the reflection mask controls surface coverage on this native pass.
    shell = material('xinzhao', 53, 0x87e94acf, tmp)
    uniforms = {'Alpha': (1,0,0,0), 'BlendMod': (1,0,0,0), 'albedoNewMin': (0,0,0,0)}
    body = bind_material(shell, '0xfd75ee', title, {
        'Diffuse_Texture': HERO, 'Mask_Texture': BODY_REFLECTION, 'MatCap_Tex': REFLECTION_LIGHT,
    }, uniforms)
    dynamic = stock[stock.index('dynamicMaterial:'):stock.rfind('}')].strip()
    fade = remove_field(dynamic, 'staticSwitch').replace('"DissolveBias"', '"Alpha"')
    assert 'IsDeadDynamicMaterialBoolDriver' in fade and 'staticSwitch:' not in fade
    body = body[:body.rfind('}')] + '    ' + fade + '\n    }'
    blade = bind_material(shell, SHEAR, '0xcd2f8b3ead95444e', {
        'Diffuse_Texture': WEAPON, 'Mask_Texture': WEAPON_REFLECTION, 'MatCap_Tex': REFLECTION_LIGHT,
    }, uniforms)
    plush = bind_material(shell, DOLL_MATERIAL, '0x0bb89665acc27bc6', {
        'Diffuse_Texture': DOLL_DIFFUSE, 'Mask_Texture': DOLL_REFLECTION, 'MatCap_Tex': REFLECTION_LIGHT,
    }, uniforms)
    return '\n'.join((body, blade, plush))

