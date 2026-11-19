"""Package evaluated Blender geometry with SKN 4.1 range-relative indices."""
import os
import json,hashlib,re,struct,subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile,ZIP_DEFLATED
import numpy as np
from core import GW,HERE,SKIN,fmt_key
from source_layout import SOURCE,OUT
from build_qw import SKIN_BIN,ANIM_BIN,convert,keep_untouched,read_json,DEFAULT_GAME,PREFIX
from q_effect import _entries
from native_materials import SHEAR,WEAPON,BODY_RMA,WEAPON_RMA,DOLL_RMA,definitions
from native_materials import BODY_REFLECTION,WEAPON_REFLECTION,REFLECTION_LIGHT,SOLID_SHADER
from native_materials import DOLL_MATERIAL,DOLL_DIFFUSE,DOLL_REFLECTION
ROOT='assets/characters/gwen/skins/base/'
HERO=ROOT+'blg_gwen_detail.tex'
MODEL=ROOT+'gwen_base.skn'
WAD='WAD/Gwen.wad.client'
VERSION='1.5.3'
DEST=SKIN/('Gwen1-BLG-'+VERSION+'.fantome')
SEED=HERE/'gameplay-resources.zip'
DT=np.dtype([('p','<f4',3),('i','u1',4),('w','<f4',4),('n','<f4',3),('uv','<f4',2)])
def sha(data):return hashlib.sha256(data).hexdigest()
def partition(v,f,limit):
    if len(v)<=limit:
        yield v,f;return
    # Split along authored face runs and duplicate only boundary vertices.
    for batch in np.array_split(f,2):
        selected,inv=np.unique(batch,return_inverse=True)
        yield from partition(v[selected],inv.reshape(-1,3),limit)
def character_sections(desc):
    chunks={}
    for r in desc['parts']:
        with np.load(OUT/'parts'/r['file']) as d:v,f=d['v'],d['f']
        assert len(f)==r['triangles'] and (r['kind']!='mesh' or len(f)==r['source_faces'])
        for vv,ff in partition(v,f,2048 if r['kind']=='fibre' else 65535):
            assert vv.dtype==DT
            chunks.setdefault(r['role'],[]).append((vv,ff))
    groups=[]
    for role,items in chunks.items():
        bins=[]
        for v,f in sorted(items,key=lambda pair:-len(pair[0])):
            slot=next((b for b in bins if b[0]+len(v)<=65535),None)
            if slot is None:slot=[0,[],[]];bins.append(slot)
            slot[1].append(v);slot[2].append(f+slot[0]);slot[0]+=len(v)
        for i,(_,vs,fs) in enumerate(bins):
            name=role if i==0 else role+str(i).zfill(2)
            faces=np.concatenate(fs);v=np.concatenate(vs)
            # The authoring renderer draws open cloth and native strand ribbons two-sided.
            if role.startswith('Body'):faces=np.concatenate((faces,faces[:,::-1]))
            groups.append((name,v,faces))
    return groups

def compile_mesh(desc,seed):
    from doll_polish import section
    groups=character_sections(desc)
    native_v,native_f=section(seed)
    with np.load(OUT/'doll-source.npz') as original:v,f=original['v'],original['f']
    assert np.array_equal(v,native_v) and np.array_equal(f,native_f),'Doll differs from Blender master'
    groups.append(('Doll',v,f))
    for name in ('Needle','Scissors_A_Smear','RecallStage'):
        v=np.frombuffer(seed.read('parts/'+name+'.vertices'),dtype=DT)
        f=np.frombuffer(seed.read('parts/'+name+'.indices'),'<u2').reshape(-1,3);groups.append((name,v,f))
    return encode_sections(groups)

def encode_sections(groups):
    assert len(groups)<=32,len(groups)
    header=bytearray(struct.pack('<IHHI',0x112233,4,1,len(groups)))
    indices=[];vertices=[];nv=ni=0;manifest={}
    lo=np.full(3,np.inf);hi=-lo
    for name,v,f in groups:
        assert f.min()>=0 and f.max()<len(v)<=65536
        assert np.isfinite(v['p']).all() and np.allclose(v['w'].sum(1),1,atol=2e-5)
        header+=struct.pack('<64s4I',name.encode(),nv,len(v),ni,f.size)
        a=f.astype('<u2').tobytes();b=v.tobytes()
        manifest[name]=[len(v),len(f),sha(a),sha(b)]
        indices.append(a);vertices.append(b);nv+=len(v);ni+=f.size
        lo=np.minimum(lo,v['p'].min(0));hi=np.maximum(hi,v['p'].max(0))
    center=(lo+hi)/2;radius=np.linalg.norm(hi-center)
    header+=struct.pack('<5I10f',2,ni,nv,52,0,*lo,*hi,*center,radius)
    result=bytes(header)+b''.join(indices)+b''.join(vertices)+bytes(12)
    # Independently re-read each named span. Check all faces, normals, UVs and weights.
    for i,(name,(vc,fc,inds,verts)) in enumerate(manifest.items()):
        label,base,count,start,n=struct.unpack_from('<64s4I',result,12+i*80)
        assert label.rstrip(b'\0').decode()==name and count==vc and n==fc*3
        off=len(header);data=result[off+2*start:off+2*(start+n)]
        assert sha(data)==inds and np.frombuffer(data,'<u2').max()<count
        off+=ni*2+base*52;assert sha(result[off:off+52*count])==verts
    return result,list(manifest),manifest
def configure(blob,path,names,tmp):
    src=tmp/'in.bin';txt=tmp/'in.rito';dst=tmp/'out.bin'
    src.write_bytes(blob);convert(src,txt);pre,entries,post=_entries(txt.read_text('utf8'))
    body=[n for n in names if n.startswith('Body')]
    def expand(m):
        key=m[2]
        if not re.search(r'\b0x0*dbaa7975\b',key):return m[0]
        return m[1]+key.rstrip()+' '+ ' '.join(fmt_key(n) for n in body[1:])+' }'
    # Keep every original visibility/effect binding on each physical Body draw.
    pattern=r'((?:m(?:Hide|Show)SubmeshList|mSubmeshesToDraw(?:Always)?|SubmeshesTo(?:Hide|Show)):\s*list2?\[hash\]\s*=\s*\{)([^{}]*)\}'
    changed=set();out=[]
    for key,kind,row in entries:
        edit=re.sub(pattern,expand,row)
        if kind=='SkinCharacterDataProperties':
            old='SkinMeshDataProperties_MaterialOverride {\n                    Material: link = 0xfd75ee\n                    submesh: string = "Body"\n                }'
            assert edit.count(old)==1
            edit=edit.replace(old,'\n                '.join(old.replace('"Body"','"'+name+'"') for name in body))
            edit=edit.replace('texture: file = 0x28d8b820a4adc6e5','texture: file = "'+WEAPON+'"\n                    Material: link = '+SHEAR)
            edit=edit.replace('texture: file = 0xad66b1f33a4b143b','texture: file = 0xad66b1f33a4b143b\n                    Material: link = '+DOLL_MATERIAL+'\n                    RoughnessMetallicAoTexture: file = "'+DOLL_RMA+'"')
            edit=edit.replace('"Body, Doll, Needle, Scissors, Scissors_A_Smear, RecallStage"','"'+', '.join(names)+'"')
        if key==0xfd75ee:edit=definitions(row,tmp)
        if edit!=row:changed.add(key)
        out.append(edit)
    txt.write_text(pre+'\n'+'\n'.join(out)+'\n'+post,'utf8');convert(txt,dst)
    result=keep_untouched(blob,dst.read_bytes(),changed)
    old=read_json(blob,tmp)['objects'];new=read_json(result,tmp)['objects']
    for k in old:
        if int(k,16) not in changed:assert new[k]==old[k]
    bind_lists={'mHideSubmeshList','mShowSubmeshList','mSubmeshesToDraw','mSubmeshesToDrawAlways','SubmeshesToHide','SubmeshesToShow'}
    def check(a,b):
        if isinstance(a,list) and isinstance(b,list):
            for left,right in zip(a,b):check(left,right)
        if isinstance(a,dict) and isinstance(b,dict):
            for k,v in a.items():
                if k in bind_lists and fmt_key('Body') in v:assert set(b[k])==set(v)|{fmt_key(n) for n in body}
                elif k in b:check(v,b[k])
    check(old,new)
    if path==SKIN_BIN:
        skin=next(x['skinMeshProperties'] for x in new.values() if 'skinMeshProperties' in x)
        mats={x['submesh']:x for x in skin['materialOverride']}
        assert all(mats[n]['Material']==mats['Body']['Material'] for n in body)
        assert 'BodyCards' not in mats and mats['Scissors']['Material']==SHEAR
        assert mats['Scissors']['texture']!=skin['texture'] and 'RoughnessMetallicAoTexture' in mats['Doll']
        files=[HERO,WEAPON,DOLL_DIFFUSE,DOLL_RMA,DOLL_REFLECTION,BODY_REFLECTION,WEAPON_REFLECTION,REFLECTION_LIGHT]
        read_hash="const {pathHash}=require(process.argv[1]);console.log(JSON.stringify(process.argv.slice(2).map(p=>'0x'+pathHash(p).toString(16))))"
        native_hash=dict(zip(files,json.loads(subprocess.check_output(['node','-e',read_hash,str(GW/'vfx/check_import.cjs'),*files],text=True))))
        def same(a,b):return int(a,16)==int(b,16)
        assert same(mats['Doll']['RoughnessMetallicAoTexture'],native_hash[DOLL_RMA])
        assert mats['Doll']['Material']==DOLL_MATERIAL and same(mats['Doll']['texture'],native_hash[DOLL_DIFFUSE])
        for name in ('Body','Scissors','Doll'):
            mat=new[mats[name]['Material']]
            assert mat['techniques'][0]['passes'][0]['shader']==SOLID_SHADER
            samplers={s['TextureName']:s['texturePath'] for s in mat['samplerValues']}
            diffuse={'Scissors':WEAPON,'Doll':DOLL_DIFFUSE}.get(name,HERO)
            assert same(samplers['Diffuse_Texture'],native_hash[diffuse])
            mask={'Scissors':WEAPON_REFLECTION,'Doll':DOLL_REFLECTION}.get(name,BODY_REFLECTION)
            assert same(samplers['Mask_Texture'],native_hash[mask])
            assert same(samplers['MatCap_Tex'],native_hash[REFLECTION_LIGHT])
            uniforms={p['name']:p.get('value') for p in mat['paramValues']}
            switches={s['name']:s.get('on',True) for s in mat['switches']}
            assert uniforms['Alpha'][0]==1 and uniforms['BlendMod'][0]==1
            assert switches['MASK_MATCAP'] and not switches['BLEND_ALPHA'] and not switches['USE_TEX_ALPHA']
        from material_variants import validate_materials
        validate_materials({name:new[mats[name]['Material']] for name in ('Body','Scissors','Doll')},tmp)
    return result
def pack():
    info=json.loads((OUT/'source.json').read_text('utf8'))
    # Older source caches included collection 10's hidden guides in the geometry and the counts.
    info['parts']=[r for r in info['parts'] if not r['name'].startswith('Cards · ')]
    assert info['source_sha']==sha(SOURCE.read_bytes())
    assert all(sha((OUT/'source-images'/file).read_bytes())==value for file,value in info['images'].items())
    assert not info['weight_stats']['vertices_over_four'],info['weight_stats']
    with ZipFile(SEED) as z,TemporaryDirectory(dir=OUT) as td:
        tmp=Path(td)
        mesh,names,ranges=compile_mesh(info,z)
        assert names.count('Scissors')==1 and not any(n.startswith('Scissors0') for n in names)
        asset={p:z.read(p) for p in z.namelist() if not p.startswith('parts/')}
        asset[MODEL]=mesh;asset[HERO]=(OUT/'surface.tex').read_bytes()
        for path,file in [(WEAPON,'weapon'),(BODY_RMA,'surface-rma'),(WEAPON_RMA,'weapon-rma')]:
            asset[path]=(OUT/(file+'.tex')).read_bytes()
        from reflection_textures import reflection_textures,reflection_mask
        asset.update(reflection_textures(OUT))
        from combat_polish import apply as polish_combat
        from recall_polish import apply as polish_recall
        from doll_polish import apply as polish_dolls
        polish_combat(asset,tmp)
        polish_recall(asset,tmp)
        polish_dolls(asset,tmp,packed_diffuse=OUT/'source-images/gwen-2233-plush.png')
        from repair_paint import decode_full
        from PIL import Image
        with Image.open(OUT/'source-images/gwen-2233-plush.png') as original:
            assert np.array_equal(np.asarray(decode_full(asset[DOLL_DIFFUSE])),np.asarray(original.convert('RGBA'))),'Doll texture differs from Blender master'
        asset[DOLL_REFLECTION]=reflection_mask(asset[DOLL_RMA])
        for path in (SKIN_BIN,ANIM_BIN):asset[path]=configure(asset[path],path,names,tmp)
        hashes={k:sha(v) for k,v in asset.items()}
        manifest=tmp/'manifest.json';manifest.write_text(json.dumps({'assetSha256':hashes}),'utf8')
        metadata=json.dumps(dict(Name='BLG Gwen',Version=VERSION,Author='BLG Gwen skin project',Description='Source geometry and dyed strand ribbons, crystal shears, QWER, 2233 dolls and championship recall.'))
        def archive(path,items):
            with ZipFile(path,'w',ZIP_DEFLATED,compresslevel=4) as f:
                f.writestr('META/info.json',metadata)
                for name,data in items:f.writestr(name,data)
        def verify(path,directory):
            tool=Path(os.environ.get('GWEN_MOD_TOOLS', GW.parents[1]/'tool/mod-tools.exe'))
            subprocess.run([str(tool),'import',str(path),str(directory),'--game:'+str(DEFAULT_GAME),'--noTFT'],check=True)
            wad=directory/WAD
            subprocess.run(['node',str(GW/'vfx/check_import.cjs'),str(manifest),str(wad)],check=True)
            return wad
        loose=tmp/'source.fantome';archive(loose,((PREFIX+k,v) for k,v in asset.items()))
        wad=verify(loose,tmp/'import')
        candidate=tmp/DEST.name;archive(candidate,[(WAD,wad.read_bytes())]);wad=verify(candidate,tmp/'again')
        with ZipFile(candidate) as zf:assert zf.testzip() is None
        # Reopen the compiled WAD. Previews read the actual resources this import produced.
        paths=tmp/'names.json';paths.write_text(json.dumps(list(asset)),'utf8')
        subprocess.run(['node',str(HERE/'fidelity_wad.cjs'),str(wad),str(paths),str(OUT/'decoded')],check=True)
        assert all(sha((OUT/'decoded'/k).read_bytes())==h for k,h in hashes.items())
        from material_variants import check_swatch_output
        check_swatch_output(OUT/'decoded', tmp)
        assert info['source_sha']==sha(SOURCE.read_bytes()),'Blender master was updated during packaging'
        candidate.replace(DEST)
    (OUT/'report.json').write_text(json.dumps(dict(source=info['source_sha'],package=sha(DEST.read_bytes()),resources=len(asset),ranges=ranges,source_faces=sum(r.get('source_faces',0) for r in info['parts']),knots=sum(r.get('knots',0) for r in info['parts']),wall_faces=info['wall_triangles']),indent=2),'utf8')
    print(DEST,len(names),'ranges',len(asset),'resources',flush=True)
if __name__=='__main__':pack()

