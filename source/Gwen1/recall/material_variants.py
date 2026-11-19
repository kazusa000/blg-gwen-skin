"""Resolve native shader requests from the compiled skin BIN and the installed shader definitions."""
import itertools
import json
import os
import subprocess
from pathlib import Path
from core import HERE
from build_qw import DEFAULT_GAME
from native_materials import installed_bin


def stage_requests(materials, shader_definitions):
    # The renderer loads normal, transition, and shadow passes with either global palette.
    requests = []
    for name, material in materials.items():
        technique, = material['techniques']
        render_pass, = technique['passes']
        shader = shader_definitions[render_pass['shader']]
        defines = {s['name']: str(int(s.get('onByDefault', False))) for s in shader.get('staticSwitches', [])}
        for switch in material.get('switches', []):
            if switch['name'] not in defines:
                raise ValueError(f"{name} refers to unknown switch {switch['name']}")
            defines[switch['name']] = str(int(switch.get('on', True)))
        defines.update(shader.get('featureDefines', {}))
        defines.update(material.get('shaderMacros', {}))
        defines.update(technique.get('shaderMacros', {}))
        defines.update(render_pass.get('shaderMacros', {}))
        dynamic = material.get('dynamicMaterial', {}).get('staticSwitch')
        states = [{dynamic['name']: value} for value in ('0','1')] if dynamic else [{}]
        passes = [(technique['name'], {}), ('shadow', {'GENERATE_SHADOW_MAP': '1'})]
        for child in material.get('childTechniques', []):
            assert child['parentName'] == technique['name']
            passes.append((child['name'], child['shaderMacros']))
        for state, (mode, extra), palette in itertools.product(states, passes, (False, True)):
            flags = {**defines, **state, **extra}
            if palette:flags['COLORPALETTE_DEFAULT'] = '1'
            requests.append({'name': name, 'pass': mode, 'shader': shader['objectPath'], 'defines': flags})
    return requests


def validate_materials(materials, tmp):
    path = tmp/'installed-shaders.json'
    installed_bin('data/shaders/shaders.bin', path)
    requests = stage_requests(materials, json.loads(path.read_text('utf8'))['objects'])
    return check_cache(requests, tmp)


def check_cache(requests, tmp):
    manifest = tmp/'variant-requests.json'
    rows = [{'name': entry['name'] + '/' + entry['pass'],
             'shaderPath': 'ASSETS/Shaders/Generated/'+entry['shader'], 'defines': entry['defines']}
            for entry in requests]
    manifest.write_text(json.dumps({'materials': rows}), 'utf8')
    cache = DEFAULT_GAME/'DATA/FINAL/ShaderCache.dx11.wad.client'
    result = subprocess.run(['node', str(HERE/'shader_cache.cjs'), str(cache), str(manifest),str(tmp)],
                            stdout=subprocess.PIPE, text=True)
    results = json.loads(result.stdout)
    if len(results) != len(rows):raise RuntimeError('Incomplete DX11 variant check')
    missing = [f"{row['material']} {stage} {row[stage]['status']} {row[stage].get('variantHash','')}"
               for row in results for stage in ('vertex','pixel') if row[stage]['status']!='available']
    if missing:raise ValueError('Unusable DX11 variants:\n'+'\n'.join(missing))
    result.check_returncode()
    print(f'DX11 verified {2*len(rows)} vertex/pixel requests against installed bytecode.',flush=True)
    return results


def check_swatch_output(decoded, tmp):
    from native_materials import HERO, WEAPON, BODY_REFLECTION, WEAPON_REFLECTION, REFLECTION_LIGHT
    from native_materials import DOLL_DIFFUSE,DOLL_REFLECTION
    from doll_polish import _load_sources
    from repair_paint import decode_full
    # Coordinates on the authored UV layout. Read the final WAD textures so
    # this still tests the new artwork when a texture is repainted.
    samples = {}
    atlas,_=_load_sources()
    doll_points=[(tile,x+w//2,y+h//2) for tile in ('face22','gold','pink_gem') for x,y,w,h in (atlas.RECT[tile],)]
    for mesh, atlas, mask_path, points in (
        ('body', HERO, BODY_REFLECTION, [('bodice',6349,1539),('fur',759,1799),('silk',4421,847)]),
        ('weapon', WEAPON, WEAPON_REFLECTION, [('blue crystal',469,1317),('pink crystal',1118,113),('hinge',3361,2908)]),
        ('doll',DOLL_DIFFUSE,DOLL_REFLECTION,doll_points)
    ):
        diffuse = decode_full((decoded/atlas).read_bytes())
        mask = decode_full((decoded/mask_path).read_bytes())
        for label,x,y in points:
            pixel = diffuse.getpixel((x,y))
            assert pixel[3]==255 and max(pixel[:3])>16, (label,pixel)
            mask_xy = (x*mask.width//diffuse.width,y*mask.height//diffuse.height)
            samples[label] = dict(mesh=mesh, diffuse=pixel, mask=mask.getpixel(mask_xy)[0])
    assert samples['face22']['mask']<samples['pink_gem']['mask']
    cap = decode_full((decoded/REFLECTION_LIGHT).read_bytes())
    (tmp/'actual-swatches.json').write_text(json.dumps(samples),'utf8')
    (tmp/'reflection-lights.json').write_text(json.dumps([cap.getpixel((0,0)),cap.getpixel((83,85))]),'utf8')
    compiler = Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    probe = tmp/'dx11_probe.exe'
    subprocess.run([str(compiler),'/nologo','/r:System.Web.Extensions.dll',
                    '/out:'+str(probe),str(HERE/'dx11_probe.cs')],check=True)
    subprocess.run([str(probe),str(tmp)],check=True)
