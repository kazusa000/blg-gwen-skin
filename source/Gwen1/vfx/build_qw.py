"""Build and round-trip the default Gwen Q/W visual override for the installed WAD."""
import argparse
import os
import hashlib
from io import BytesIO
import json
from pathlib import Path
import struct
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
STOCK = HERE.parent/'rig-study'
ROOT = HERE.parents[2]
SKIN = ROOT/'skin'/'Gwen1'
HASHES = Path(os.environ.get('GWEN_HASHES', ROOT/'tool'/'hashes'))
RITO = Path(os.environ.get('GWEN_RITOBIN', ROOT/'tool'/'ritobin-0.2.3'/'ritobin-tools.exe'))
BUILD = HERE/'build'
PREFIX = 'WAD/Gwen.wad.client/'
ASSETS = 'assets/characters/gwen/skins/base/particles/blg_qw/'
SKIN_BIN = 'data/characters/gwen/skins/skin0.bin'
ANIM_BIN = 'data/characters/gwen/animations/skin0.bin'
DEFAULT_GAME = Path(os.environ.get('GWEN_GAME', 'C:/Riot Games/League of Legends/Game'))
SOURCE_NAMES = {SKIN_BIN:'skin0', ANIM_BIN:'animation-skin0'}
OUTPUT = SKIN/'Gwen1-BLG-QW.fantome'


def ritobin_args():
    # Bindings are keyed by numbers. A user's shared Mimir cache may name those keys.
    empty = BUILD/'empty-hash-cache'
    empty.mkdir(parents=True,exist_ok=True)
    return [str(RITO),'-L','error','--hashtable-dir',str(empty),'-H',str(HASHES)]


def convert(source, dest):
    subprocess.run([*ritobin_args(),'convert',str(source),'-o',str(dest)],check=True)


def read_json(data, tmp):
    p = tmp/'decode.bin'
    p.write_bytes(data)
    out = p.with_suffix('.json')
    convert(p,out)
    return json.loads(out.read_text(encoding='utf-8'))


def entries(data):
    if data[:8] != b'PROP\x03\x00\x00\x00':
        raise ValueError('Expected a PROP v3 file')
    at = 12
    for _ in range(struct.unpack_from('<I',data,8)[0]):
        at += 2 + struct.unpack_from('<H',data,at)[0]
    head = data[:at]
    count = struct.unpack_from('<I',data,at)[0]
    at += 4
    types = struct.unpack_from(f'<{count}I',data,at)
    at += count*4
    blocks = {}
    for typ in types:
        size,key = struct.unpack_from('<II',data,at)
        assert key not in blocks
        blocks[key] = (typ,data[at:at+size+4])
        at += size+4
    assert at==len(data)
    return head,blocks


def keep_untouched(original, compiled, changed):
    head,old = entries(original)
    new_head,new = entries(compiled)
    assert head==new_head and set(old)<=set(new)
    rows = [(new[k] if k in changed or k not in old else old[k]) for k in new]
    return head+struct.pack('<I',len(rows))+b''.join(struct.pack('<I',t) for t,_ in rows)+b''.join(b for _,b in rows)


def strings(obj):
    if isinstance(obj,dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj,list):
        for v in obj:
            yield from strings(v)
    elif isinstance(obj,str):
        yield obj


def is_qw(name):
    name = name.lower()
    return ('_q_' in name or '_w_' in name or 'blg_q' in name or 'blg_w' in name)


def validate_scope(path, old, new, changes, combat=False, ultimate=False):
    from combat_effect import DASH_NODE, SYSTEMS
    from r_effect import SYSTEMS as R_SYSTEMS, ORBIT_NODES
    assert old['links']==new['links']
    for k in changes:
        target = new['objects'][k]
        prev = old['objects'].get(k)
        kind = target['~class']
        if path==SKIN_BIN:
            if kind=='ResourceResolver':
                for alias,dest in target['resourceMap'].items():
                    if prev['resourceMap'].get(alias)!=dest:
                        assert dest in new['objects'] and new['objects'][dest]['~class']=='VfxSystemDefinitionData'
                assert set(prev['resourceMap'])<=set(target['resourceMap'])
            else:
                name=target.get('particleName','')
                assert kind=='VfxSystemDefinitionData' and (is_qw(name) or not prev or (combat and name in SYSTEMS) or (ultimate and name in R_SYSTEMS)),(k,kind)
        else:
            assert kind=='AnimationGraphData'
            inventory=json.loads((STOCK/'graph_inventory.json').read_text(encoding='utf-8'))
            skill_nodes={int(r['graphClipKey'],16) for r in inventory['clips'] if r['slot'] in ('Q','W')}
            if combat:
                skill_nodes.add(DASH_NODE)
            if ultimate:
                skill_nodes.update(ORBIT_NODES)
            skill_nodes.update(int(node['graphClipKey'],16) for node in inventory['graphComposition']['clipDataMap']
                               if any((p.get('resolvedClipId') or '').startswith(('spell1','spell2')) for p in node['pairs']))
            for field in set(prev)|set(target):
                if field!='mClipDataMap':
                    assert prev.get(field)==target.get(field),field
            nodes = target['mClipDataMap']
            assert nodes.keys()==prev['mClipDataMap'].keys()
            for key,node in nodes.items():
                base = prev['mClipDataMap'][key]
                if base!=node:
                    assert int(key,16) in skill_nodes,('non-Q/W node changed',key)
                    assert {p:v for p,v in base.items() if p!='mEventDataMap'}=={p:v for p,v in node.items() if p!='mEventDataMap'}


def compile_override(path,base,edited,work,combat=False,ultimate=False):
    name = SOURCE_NAMES[path]
    original = (STOCK/(name+'.bin')).read_bytes()
    text = work/(name+'.rito')
    binary = text.with_suffix('.bin')
    text.write_text(base,encoding='utf-8')
    convert(text,binary)
    roundtrip = read_json(binary.read_bytes(),work)
    text.write_text(edited,encoding='utf-8')
    convert(text,binary)
    compiled = binary.read_bytes()
    target = read_json(compiled,work)
    changed = {k for k,v in target['objects'].items() if roundtrip['objects'].get(k)!=v}
    assert set(roundtrip['objects'])<=set(target['objects'])
    validate_scope(path,roundtrip,target,changed,combat,ultimate)
    # RitoBin's text writer strips trailing blanks from some stock emitter names.
    # Copy every untouched object verbatim from the installed BIN, and keep all links.
    data = keep_untouched(original,compiled,{int(k,16) for k in changed})
    decoded = read_json(data,work)
    pristine = read_json(original,work)['objects']
    assert all(v==(target['objects'][k] if k in changed else pristine[k]) for k,v in decoded['objects'].items())
    return data,decoded,changed


def encode_tex(image):
    # Native TEX format 12 stores BC3 levels in smallest-to-largest order.
    im = image.convert('RGBA')
    w,h = im.size
    assert w>0 and h>0 and not w&(w-1) and not h&(h-1)
    blocks = []
    while True:
        buf = BytesIO()
        im.save(buf,format='DDS',pixel_format='DXT5')
        dds = buf.getvalue()
        assert dds[84:88]==b'DXT5'
        blocks.append(dds[128:])
        if im.size==(1,1):
            break
        im = im.resize((max(1,im.width//2),max(1,im.height//2)),Image.Resampling.LANCZOS)
    return struct.pack('<4sHH4B',b'TEX\x00',w,h,1,12,0,1)+b''.join(reversed(blocks))


def check_tex(data,source):
    magic,w,h,kind,fmt,flags,mips = struct.unpack_from('<4sHH4B',data)
    assert (magic,kind,fmt,flags,mips)==(b'TEX\x00',1,12,0,1) and (w,h)==source.size
    sizes = []
    a,b = w,h
    while True:
        sizes.append(16*((a+3)//4)*((b+3)//4))
        if a==b==1:
            break
        a,b = max(1,a//2),max(1,b//2)
    assert len(data)==12+sum(sizes)
    template=BytesIO()
    Image.new('RGBA',(4,4)).save(template,format='DDS',pixel_format='DXT5')
    header=bytearray(template.getvalue()[:128])
    struct.pack_into('<III',header,12,h,w,sizes[0])
    decoded=np.asarray(Image.open(BytesIO(header+data[-sizes[0]:])).convert('RGBA'),dtype='f')/255
    authored=np.asarray(source.convert('RGBA'),dtype='f')/255
    # Quantization of transparent pixels' RGB is irrelevant to the blended result.
    assert np.abs(decoded[:,:,3]-authored[:,:,3]).mean()<.03
    err=np.abs(decoded[:,:,:3]*decoded[:,:,3:]-authored[:,:,:3]*authored[:,:,3:]).mean()
    assert err<.06,err


def build(game,combat=False,ultimate=False):
    import q_effect
    import w_effect
    BUILD.mkdir(exist_ok=True)
    wad = game/'DATA'/'FINAL'/'Champions'/'Gwen.wad.client'
    digests = json.loads(subprocess.check_output(['node',str(HERE/'check_stock.cjs'),str(wad),str(STOCK)],text=True))
    version=json.loads((game/'compat-version-metadata.json').read_text(encoding='utf-8'))['version'].split('+')[0]
    texts=[(STOCK/(n+'_named.rito')).read_text(encoding='utf-8') for n in SOURCE_NAMES.values()]
    s,a = q_effect.apply(*texts)
    s,a = w_effect.apply(s,a)
    from champion_art import paint
    paint()
    output=OUTPUT
    combat=combat or ultimate
    if combat:
        import combat_art
        import combat_effect
        s,a=combat_effect.apply(s,a)
        combat_art.paint()
        output=SKIN/'Gwen1-BLG-QWE.fantome'
    if ultimate:
        import r_art
        import r_effect
        import r_mesh
        s=r_effect.apply(s)
        a=r_effect.bind_orbit(a)
        mesh_names=r_mesh.build()
        r_art.paint()
        output=SKIN/'Gwen1-BLG-QWER-v5.fantome'
    changes,decoded,assets = {},{},{}
    with TemporaryDirectory(dir=BUILD) as directory:
        work=Path(directory)
        for path,old,edited in zip(SOURCE_NAMES,texts,(s,a)):
            data,decoded[path],changes[path] = compile_override(path,old,edited,work,combat,ultimate)
            if changes[path]:
                assets[path] = data
        names={v.lower() for tree in decoded.values() for v in strings(tree) if ASSETS in v.lower()}
        assert any('/q_' in n for n in names) and any('/w_' in n for n in names)
        for name in sorted(names):
            assert name.startswith(ASSETS) and '..' not in name and name.endswith('.tex'),name
            with Image.open(HERE/'art'/(Path(name).stem+'.png')) as im:
                assets[name]=encode_tex(im)
        if ultimate:
            meshes={p for p in strings(decoded[SKIN_BIN]) if p.startswith(r_mesh.MESH_ROOT)}
            assert meshes=={r_mesh.MESH_ROOT+stem+'.scb' for stem in mesh_names}
            for name in meshes:
                assets[name]=(r_mesh.MESH_DIR/Path(name).name).read_bytes()
        meta={'Name':'Gwen BLG - Q and W','Author':'Gwen1 skin project','Version':'0.3.0',
              'Description':'BLG crystal shears and embroidered mist for default Gwen. Q/W visual effects only. Built for '+version+'.',
              'Champions':['Gwen'],'Tags':['vfx']}
        if combat:
            meta.update(Name='Gwen BLG - Q, W, E and basic attack hits',Version='0.4.1',
                        Description='BLG crystal shears, trophy mist, Skip ’n Slash and basic attack hits for default Gwen. Built for '+version+'.')
        if ultimate:
            meta.update(Name='Gwen BLG - Q, W, E, R and basic attack hits',Version='0.8.1',
                        Description='Needlework with continuous crystal mist trails, a flowing eye veil and orbiting pearl haze, with BLG Q/W/E and basic attack hits. Built for '+version+'.')
        staged=work/output.name
        with ZipFile(staged,'w',ZIP_DEFLATED,compresslevel=7) as z:
            z.writestr('META/info.json',json.dumps(meta,ensure_ascii=False,indent=2))
            for dest,blob in sorted(assets.items()):
                z.writestr(PREFIX+dest,blob)
        with ZipFile(staged) as z:
            assert z.testzip() is None and len(z.infolist())==len(assets)+1
            assert json.loads(z.read('META/info.json'))==meta
            for path in SOURCE_NAMES:
                if path in assets:
                    assert read_json(z.read(PREFIX+path),work)==decoded[path]
            for n in names:
                with Image.open(HERE/'art'/(Path(n).stem+'.png')) as im:
                    check_tex(z.read(PREFIX+n),im)
        report={'gameVersion':version,'stockSha256':digests,'changedObjects':{k:sorted(v) for k,v in changes.items()},
                'assetSha256':{k:hashlib.sha256(v).hexdigest() for k,v in assets.items()},'archiveBytes':staged.stat().st_size,
                'sha256':hashlib.sha256(staged.read_bytes()).hexdigest()}
        report_name='ultimate-archive-check.json' if ultimate else 'combat-archive-check.json' if combat else 'archive-check.json'
        (BUILD/report_name).write_text(json.dumps(report,indent=2),encoding='utf-8')
        staged.replace(output)
    print(version,output,output.stat().st_size,'bytes;',len(names),'TEX resources',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--game',type=Path,default=DEFAULT_GAME)
    parser.add_argument('--combat',action='store_true')
    parser.add_argument('--ultimate',action='store_true')
    args=parser.parse_args()
    build(args.game,args.combat,args.ultimate)
