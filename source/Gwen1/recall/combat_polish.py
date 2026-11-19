"""Patch the 1.4.2 gameplay seed's E, attack-hit and R particle objects.

The seed already contains BLG Q/W/E/R assets.  This module edits just the
existing E/BA/R-missile VFX blocks and their E/R TEX resources, preserving
the original BIN records for every object outside that scope.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GW = HERE.parent
VFX = GW / 'vfx'
if str(VFX) not in sys.path:
    sys.path.insert(0, str(VFX))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from build_qw import (ANIM_BIN, SKIN_BIN, convert, keep_untouched, read_json,
                      strings)
from q_effect import _entries, _matching_brace
from w_effect import ASSET_ROOT


def _as_path(value):
    if isinstance(value, (str, Path)):
        return Path(value)
    return Path(value.name)


def _polish_skin(text):
    import combat_effect
    import r_effect

    prefix, records, suffix = _entries(text)
    e_changed = set()
    r_changed = set()
    out = []
    for key, kind, block in records:
        if kind == 'VfxSystemDefinitionData':
            match = re.search(r'particleName: string = "([^"]+)"', block)
            name = match[1] if match else ''
            if name in combat_effect.SYSTEMS:
                block = combat_effect.edit_system(name, block)
                e_changed.add(name)
            elif name in ('Gwen_Base_R_Missile', 'Gwen_Base_R_Missile02'):
                block = r_effect.missile(block, name.endswith('02'))
                r_changed.add(name)
            if name in combat_effect.SYSTEMS or name in ('Gwen_Base_R_Missile', 'Gwen_Base_R_Missile02'):
                emitter_names = re.findall(r'emitterName: string = "([^"]+)"', block)
                assert len(emitter_names) == len(set(emitter_names)), name
        out.append(block)

    assert e_changed == combat_effect.SYSTEMS, sorted(e_changed)
    assert r_changed == {'Gwen_Base_R_Missile', 'Gwen_Base_R_Missile02'}, sorted(r_changed)
    return prefix + '\n' + '\n'.join(out) + '\n' + suffix, e_changed | r_changed


def _compile_skin(original, tmp):
    src = tmp / 'combat-polish-input.bin'
    rito = tmp / 'combat-polish-output.rito'
    compiled = tmp / 'combat-polish-output.bin'
    src.write_bytes(original)
    convert(src, rito)
    base = rito.read_text(encoding='utf-8')
    polished, systems = _polish_skin(base)
    rito.write_text(polished, encoding='utf-8')
    convert(rito, compiled)

    before = read_json(original, tmp)['objects']
    compiled_objects = read_json(compiled.read_bytes(), tmp)['objects']
    changed = {int(key, 16) for key, value in compiled_objects.items()
               if before.get(key) != value}
    allowed_names = systems
    changed_names = {compiled_objects[key]['particleName'] for key in compiled_objects
                     if int(key, 16) in changed and 'particleName' in compiled_objects[key]}
    assert changed_names <= allowed_names, sorted(changed_names - allowed_names)
    required_names = {
        'Gwen_Base_E_ATKSPD_Buff', 'Gwen_Base_E_ATK_Swing', 'Gwen_Base_E_Impact01',
        'Gwen_Base_BA_Impact01', 'Gwen_Base_BA_Impact02', 'Gwen_Base_BA_Impact03',
        'Gwen_Base_R_Missile', 'Gwen_Base_R_Missile02',
    }
    assert required_names <= changed_names, sorted(required_names - changed_names)

    result = keep_untouched(original, compiled.read_bytes(), changed)
    final = read_json(result, tmp)['objects']
    assert set(final) == set(before)
    for key in before:
        if int(key, 16) not in changed:
            assert final[key] == before[key], key
    # Q and W object payloads must remain byte-equivalent at the decoded level.
    for key, row in before.items():
        name = row.get('particleName', '')
        if re.search(r'(?:_Q_|_W_|_Q$|_W$)', name):
            assert final[key] == row, name
    final_bin = tmp / 'combat-polish-verified.bin'
    final_rito = tmp / 'combat-polish-verified.rito'
    final_bin.write_bytes(result)
    convert(final_bin, final_rito)
    _verify_compiled_text(final_rito.read_text(encoding='utf-8'), changed_names)
    # Validate emitter-name uniqueness from the compiled payload as well.
    for key, row in final.items():
        name = row.get('particleName', '')
        if name not in changed_names:
            continue
        emitter_names = list(_collect_emitters(row))
        assert len(emitter_names) == len(set(emitter_names)), name
    return result, changed_names, final


def _emitter_block(system_block, name):
    name_match = re.search(r'emitterName: string = "' + re.escape(name) + r'"', system_block)
    assert name_match, name
    start = system_block.rfind('VfxEmitterDefinitionData {', 0, name_match.start())
    assert start >= 0, name
    brace = system_block.find('{', start)
    return system_block[start:_matching_brace(system_block, brace)]


def _verify_compiled_text(text, changed):
    _, records, _ = _entries(text)
    systems = {}
    for _, kind, block in records:
        if kind != 'VfxSystemDefinitionData':
            continue
        match = re.search(r'particleName: string = "([^"]+)"', block)
        if match and match[1] in changed:
            systems[match[1]] = block
    assert set(systems) == set(changed)

    glow = _emitter_block(systems['Gwen_Base_E_ATKSPD_Buff'], 'Weapon_Avatar_Glow1')
    assert abs(_scalar(glow, 'timeBeforeFirstEmission')-.025) < 1e-5
    assert abs(_scalar(glow, 'rate')-2.2) < 1e-4
    assert abs(_scalar(glow, 'particleLifetime')-1.7) < 1e-4
    glow_color = _vector(glow, 'birthColor', 4)
    assert all(abs(a-b) < 1e-5 for a,b in zip(glow_color, (1,1,1,.8)))
    assert 'pass: i16 = 30' in glow and 'blendMode: u8 = 4' in glow
    uv_rate = _vector(glow, 'birthUvScrollRate', 2, optional=True) or (0.0, 0.0)
    assert max(abs(value) for value in uv_rate) < 1e-6
    assert re.search(r'mSubmeshesToDraw: list\[hash\] = \{\s*0x0*9f0bcf6\s*\}', glow)

    sweep = _emitter_block(systems['Gwen_Base_E_ATKSPD_Buff'], 'BLG_E_BladeSweep')
    assert 'pass: i16 = 31' in sweep and 'blendMode: u8 = 4' in sweep
    assert abs(_scalar(sweep, 'timeBeforeFirstEmission')-.035) < 1e-5
    assert abs(_scalar(sweep, 'rate')-3.1) < 1e-4
    assert abs(_scalar(sweep, 'particleLifetime')-1.05) < 1e-4
    sweep_scroll = _vector(sweep, 'birthUvScrollRate', 2)
    assert all(abs(a-b) < 1e-5 for a,b in zip(sweep_scroll, (.32,-.11)))
    assert re.search(r'mSubmeshesToDraw: list\[hash\] = \{\s*0x0*9f0bcf6\s*\}', sweep)

    for system in ('Gwen_Base_R_Missile', 'Gwen_Base_R_Missile02'):
        block = systems[system]
        emitters = re.findall(r'emitterName: string = "([^"]+)"', block)
        assert len(emitters) == len(set(emitters)), system
        assert not any(name.startswith(('LongGeo_Strands', 'TrailCenter', 'Strands_Ribbon', 'HoneyTrail',
                                        'BLG_R_ConnectedMist_', 'Sparkles', 'SmallStarTrail')) for name in emitters)
        wake = _emitter_block(block, 'BLG_R_FlightWake')
        assert 'VfxPrimitiveMesh {' in wake and 'isSingleParticle: flag = true' in wake
        assert 'r_flight_wake.scb"' in wake and 'r_flight_wake.tex"' in wake
        assert abs(_scalar(wake, 'bindWeight') - 1.) < 1e-6
        assert 'SeparateLingerColor:' in wake and 'textureMult:' not in wake
        assert 'VfxPrimitiveArbitraryTrail' not in block and block.count('VfxPrimitiveCameraTrail') == 2
        for label in ('BLG_R_WindBlue','BLG_R_WindRose'):
            trail = _emitter_block(block,label)
            assert 'VfxPrimitiveCameraTrail' in trail and 'emitOffset:' in trail
            assert 'r_wind_fibre.tex"' in trail and 'alphaErosionDefinition' not in trail
            assert _scalar(trail,'rate') >= 80 and 'textureMult:' not in trail
        assert 'Generic_GlowSoft.tex' in _emitter_block(block,'BLG_R_EyeLight')
        glint = _emitter_block(block,'BLG_R_TipGlint')
        assert 'r_tip_glint.scb"' in glint and 'blendMode: u8 = 4' in glint
        face = _emitter_block(block,'NEEDLDMESH1' if system.endswith('02') else 'NEEDLDMESH')
        assert 'r_projectile.scb"' in face and 'r_projectile_' in face
        assert all(abs(actual-expected)<1e-5 for actual,expected in
                   zip(_vector(face,'birthScale0',3),(1.67,1.63,1.19)))
    for name, block in systems.items():
        emitters = re.findall(r'emitterName: string = "([^"]+)"', block)
        assert len(emitters) == len(set(emitters)), name


def _field_block(text, name, optional=False):
    match = re.search(r'(?m)^\s*'+re.escape(name)+r':\s*[^\n]*?\{', text)
    if not match:
        assert optional, name
        return None
    brace = text.find('{', match.start(), match.end())
    return text[match.start():_matching_brace(text, brace)]


def _numbers(value):
    return tuple(float(number) for number in re.findall(
        r'(?<![\w.])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?', value))


def _scalar(text, name):
    direct = re.search(r'(?m)^\s*'+re.escape(name)+r':\s*f32\s*=\s*([-+\d.eE]+)', text)
    if direct:
        return float(direct[1])
    block = _field_block(text, name)
    match = re.search(r'constantValue:\s*f32\s*=\s*([-+\d.eE]+)', block)
    assert match, name
    return float(match[1])


def _vector(text, name, count, optional=False):
    block = _field_block(text, name, optional)
    if block is None:
        return None
    match = re.search(r'constantValue:\s*vec\d\s*=\s*\{([^}]*)\}', block, re.S)
    assert match, name
    numbers = _numbers(match[1])
    assert len(numbers) == count, (name, numbers)
    return numbers


def _collect_emitters(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == 'emitterName' and isinstance(item, str):
                yield item
            else:
                yield from _collect_emitters(item)
    elif isinstance(value, list):
        for item in value:
            yield from _collect_emitters(item)


def _texture_sources():
    import combat_art
    import r_art

    combat_art.paint()
    r_art.paint()
    _make_blade_uv_art(combat_art.ART / 'e_blade_facets.png')
    return {
        'e_blade_facets': combat_art.ART / 'e_blade_facets.png',
        'e_blade_sweep': combat_art.ART / 'e_blade_sweep.png',
        'combat_star_ice': combat_art.ART / 'combat_star_ice.png',
        'combat_star_rose': combat_art.ART / 'combat_star_rose.png',
        'r_flow_ice': combat_art.ART / 'r_flow_ice.png',
        'r_flow_rose': combat_art.ART / 'r_flow_rose.png',
        'r_flight_wake': combat_art.ART / 'r_flight_wake.png',
        'r_wind_fibre': combat_art.ART / 'r_wind_fibre.png',
        'r_projectile_ice': combat_art.ART / 'r_projectile_ice.png',
        'r_projectile_crown': combat_art.ART / 'r_projectile_crown.png',
    }


def _make_blade_uv_art(path):
    """Paint a moving jewel reflection in the actual prismatic-glass UV tile.

    The Scissors draw is a single attached submesh, but its atlas UV puts the
    two blade enamel faces in the Prismatic glass inlay tile. Matching that
    tile keeps the buff off the gold ribs, television, hinge and finger loops.
    """
    import numpy as np
    from PIL import Image
    from source_layout import OUT, WEAPON_CROPS, WEAPON_SIZE, WEAPON_TILES

    size = 1024
    x, y, w, h = WEAPON_TILES['Prismatic glass inlay']
    # source_paint.atlas() places each tile into its authored UV rectangle
    # with a four-pixel edge gutter; use the same crop and scale here.
    box = WEAPON_CROPS['Prismatic glass inlay']
    source = Image.open(OUT / 'source-images' / 'scissors.png').convert('RGB')
    tile = source.crop(box)
    tw, th = round(size*w/WEAPON_SIZE[0]), round(size*h/WEAPON_SIZE[1])
    tx, ty = round(size*x/WEAPON_SIZE[0]), round(size*y/WEAPON_SIZE[1])
    rgb = np.asarray(tile.resize((tw, th), Image.Resampling.LANCZOS)).astype('f') / 255
    lo = rgb.min(axis=2)
    hi = rgb.max(axis=2)
    chroma = hi-lo
    r, g, b = rgb.transpose(2, 0, 1)
    blue = np.clip((b-r-.035)/.33, 0, 1) * np.clip((b-g+.04)/.26, 0, 1)
    rose = np.clip((r-g-.045)/.30, 0, 1) * np.clip((r-b+.035)/.26, 0, 1)
    coverage = np.clip((chroma-.055)/.24, 0, 1) * np.clip((hi-.16)/.40, 0, 1)
    blue *= coverage
    rose *= coverage
    mask = np.maximum(blue, rose)
    assert mask.max() > .3 and np.count_nonzero(mask > .25) > 300

    u = (np.arange(tw, dtype='f')[None, :] + .5) / tw
    v = (np.arange(th, dtype='f')[:, None] + .5) / th
    sweep = .5 + .5*np.cos(2*np.pi*(3.4*u + .52*v + .11*np.sin(2*np.pi*v)))
    facet = .72 + .18*sweep + .10*(.5+.5*np.cos(2*np.pi*(9*u-1.4*v)))
    blue_tint = np.array([.12, .58, 1.0])
    rose_tint = np.array([1.0, .17, .65])
    weight = rose/(blue+rose+1e-8)
    tint = blue_tint[None,None,:]*(1-weight[...,None]) + rose_tint[None,None,:]*weight[...,None]
    glint = np.exp(-((np.sin(2*np.pi*(2.6*u+v*.29)))/.065)**2) * (.5+.5*sweep)
    color = np.clip(tint*facet[...,None] + glint[...,None]*.19, 0, 1)
    alpha = np.clip(mask*(.55+.27*sweep), 0, .82)
    rgba = np.zeros((size, size, 4), dtype='uint8')
    rgba[ty:ty+th, tx:tx+tw, :3] = np.rint(color*255).astype('uint8')
    rgba[ty:ty+th, tx:tx+tw, 3] = np.rint(alpha*255).astype('uint8')
    # Painted glass contains nearly white facets, so colour keying alone loses
    # much of its silhouette. Trace the two actual blade-face UV islands.
    from PIL import ImageDraw,ImageFilter
    parts=json.loads((OUT/'source.json').read_text('utf8'))['parts']
    for part in (row for row in parts if 'ground crystal blade' in row['name']):
        mesh=OUT/'parts'/part['file'];material_ids=np.load(mesh.with_name(mesh.stem+'-materials.npy'))
        layer=Image.new('L',(size,size));draw=ImageDraw.Draw(layer)
        with np.load(mesh) as data:
            faces=data['f'][material_ids==part['materials'].index('BLG / Prismatic glass inlay')]
            points=np.rint(data['v']['uv'][faces]*size-.5).astype('i')
        for triangle in points:draw.polygon([tuple(p) for p in triangle],fill=255)
        inside=np.asarray(layer)>0
        edge=np.asarray(layer,dtype='f')/255-np.asarray(layer.filter(ImageFilter.MinFilter(9)),dtype='f')/255
        yy,xx=np.nonzero(inside)
        p=(xx-tx+.5)/tw;q=(yy-ty+.5)/th
        plane=.5+.5*np.sin(2*np.pi*(q*2.2+p*1.55))
        seam=np.exp(-(np.sin(np.pi*(q*3.8+p*2.9))/.08)**2)
        ice=part['name'].startswith('Azure')
        dye=np.array([20,138,250] if ice else [247,46,157])
        tip=np.array([96,238,255] if ice else [255,143,222])
        radiance=np.maximum(.74*edge[yy,xx],.66*seam)
        rgba[yy,xx,:3]=np.rint(dye*(1-radiance[:,None])+tip*radiance[:,None]).astype('u1')
        rgba[yy,xx,3]=np.rint(255*np.minimum(1,.65+.16*plane+.25*radiance)).astype('u1')
    rgba[rgba[:,:,3] == 0, :3] = 0
    Image.fromarray(rgba, 'RGBA').save(path)


def _prepare_particle(stem):
    """Build premultiplied RGBA particle textures with UV-aware edge rules."""
    import numpy as np
    from PIL import Image
    from repair_paint import ART, bitmap

    src = np.asarray(Image.open(ART/(stem+'.png')).convert('RGBA')).astype('f')/255
    h, w = src.shape[:2]
    y, x = np.mgrid[:h, :w]
    if stem.startswith('r_projectile_'):
        src[...,:3] *= src[...,3:]
        return bitmap(src*255)
    if stem in ('r_flow_ice', 'r_flow_rose', 'r_wind_fibre'):
        # r_flow scrolls and wraps in U. Feather only the V ends, so neither
        # vertical edge gets cleared and the trail never opens a hard seam.
        dist = np.minimum(y, h-1-y)/h
        edge = np.clip((dist-.016)/.07, 0, 1)
        edge = edge**2*(3-2*edge)
        alpha = src[...,3]*edge
        rgba = np.dstack((src[...,:3]*alpha[...,None]**.82*np.array([.91,.93,.98]), alpha))
        # A periodic source should meet at its U boundary after V feathering.
        assert np.abs(rgba[:,0,:]-rgba[:,-1,:]).mean() < .045
        rgba[rgba[...,3] < 2/255, :3] = 0
        return bitmap(rgba*255)
    if stem == 'e_blade_facets':
        # The source PNG is already clipped to the two blade inlay UV islands;
        # do not apply the older V-centre mask that blanked those actual faces.
        alpha = src[...,3]*.80
        rgba = np.dstack((src[...,:3]*alpha[...,None]**.82*np.array([.91,.93,.98]), alpha))
        rgba[rgba[...,3] < 2/255, :3] = 0
        return bitmap(rgba*255)
    from repair_paint import particle
    return particle(stem)


def apply(assets, tmp):
    """Mutate a gameplay SEED asset dict with the E/AA/R polish.

    `assets` maps game/WAD resource paths to bytes. `tmp` is a writable scratch
    directory. The function leaves Q/W, model, animation and recall resources
    untouched; it does not write or replace a final package.
    """
    tmp = _as_path(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    assert SKIN_BIN in assets and ANIM_BIN in assets
    before_skin = assets[SKIN_BIN]
    before_anim = assets[ANIM_BIN]
    data, changed, decoded = _compile_skin(before_skin, tmp)
    assets[SKIN_BIN] = data

    roots = _texture_sources()
    written = []
    from repair_paint import encode_particle
    from r_mesh import MESH_ROOT, flight_wake, projectile, tip_glint
    wake_path = MESH_ROOT + 'r_flight_wake.scb'
    assets[wake_path] = flight_wake().encode()
    projectile_path = MESH_ROOT + 'r_projectile.scb'
    assets[projectile_path] = projectile().encode()
    glint_path = MESH_ROOT + 'r_tip_glint.scb'
    assets[glint_path] = tip_glint().encode()
    for stem, source in roots.items():
        target = ASSET_ROOT + stem + '.tex'
        assert target in assets or stem in ('e_blade_sweep','r_flight_wake','r_wind_fibre',
                                           'r_projectile_ice','r_projectile_crown'), f'Missing baseline texture {target}'
        # Re-read the authored PNG through the project's premultiplied particle
        # path. Format 20 keeps transparent RGB exactly zero at every mip,
        # avoiding light-fringe blocks from BC endpoint colors in alpha fringes.
        image = _prepare_particle(stem)
        encoded = encode_particle(image)
        _check_zero_transparent_mips(encoded)
        assets[target] = encoded
        written.append(target)

    refs = {s.lower() for s in strings(decoded)}
    assert {wake_path,projectile_path,glint_path} <= refs
    assert all(path.lower() in refs for path in written)

    assert assets[ANIM_BIN] == before_anim
    hashes = {name: hashlib.sha256(assets[name]).hexdigest()
              for name in [SKIN_BIN, *written]}
    return {'changedSystems': sorted(changed), 'textures': sorted(written),
            'preservedAnimation': assets[ANIM_BIN] == before_anim,
            'unchangedQW': True, 'sha256': hashes}


def _check_zero_transparent_mips(data):
    magic, width, height, kind, fmt, flags, mips = struct.unpack_from('<4sHH4B', data)
    assert magic == b'TEX\0' and kind == 1 and fmt == 20 and flags == 0 and mips == 1
    # Format 20 stores BGRA, smallest mip first, then doubles toward the source.
    dimensions = []
    w, h = width, height
    while True:
        dimensions.append((w, h))
        if w == h == 1:
            break
        w, h = max(1, w//2), max(1, h//2)
    assert sum(w*h*4 for w,h in dimensions) + 12 == len(data), dimensions
    offset = 12
    for w, h in reversed(dimensions):
        size = w*h*4
        raw = data[offset:offset + size]
        offset += size
        for index in range(0, size, 4):
            if raw[index + 3] == 0:
                assert raw[index:index + 3] == b'\0\0\0'
