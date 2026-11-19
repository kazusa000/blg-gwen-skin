"""Author, export, and texture the full paired 22/33 plush mesh from one source."""
from __future__ import annotations

import importlib.util
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
GW = HERE.parent
PLUSH = GW / 'plush_2233'
ROOT = 'assets/characters/gwen/skins/base/'
TEXTURE = ROOT + 'blg_2233_doll.tex'
DOLL_RMA = ROOT + 'blg_2233_textile_rma.tex'
SKL = ROOT + 'gwen_base.skl'
DT = np.dtype([('p','<f4',3),('i','u1',4),('w','<f4',4),('n','<f4',3),('uv','<f4',2)])

_modules = None


def _load_sources():
    """Load the Gwen doll modules by path, avoiding same-named champion helpers."""
    global _modules
    if _modules is not None:
        return _modules
    def module(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        obj = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(obj)
        return obj
    old = sys.modules.get('atlas')
    atlas = module('_gwen_plush_atlas', PLUSH / 'atlas.py')
    sys.modules['atlas'] = atlas
    try:
        model = module('_gwen_plush_model', PLUSH / 'model.py')
    finally:
        if old is None:
            sys.modules.pop('atlas', None)
        else:
            sys.modules['atlas'] = old
    _modules = (atlas, model)
    return _modules


def _skeleton(seed):
    blob = seed.read(SKL)
    if struct.unpack_from('<I', blob, 4)[0] != 0x22FD4FC3:
        raise ValueError('Doll seed has an unexpected SKL header')
    count, influence_count, joint_offset, _, influence_offset = struct.unpack_from('<HIIII', blob, 14)
    joints = []
    for i in range(count):
        row = joint_offset + i * 100
        index, parent = struct.unpack_from('<Hh', blob, row + 2)
        if index != i:
            raise ValueError(f'SKL joint table is not ordered at {i}')
        name_at = row + 96 + struct.unpack_from('<i', blob, row + 96)[0]
        joints.append(blob[name_at:blob.index(0, name_at)].decode('utf8'))
    influences = np.frombuffer(blob, '<u2', influence_count, influence_offset).copy()
    parents = np.array([struct.unpack_from('<h', blob, joint_offset + i * 100 + 4)[0]
                        for i in range(count)], dtype=np.int16)
    return joints, influences, parents


def _mesh(seed):
    atlas, model_module = _load_sources()
    model = model_module.build_model()
    points = np.asarray(model.p, dtype=np.float32)
    faces = np.asarray(model.tri, dtype=np.int64)
    tiles = np.asarray(model.face_tiles, dtype='U24')
    if len(tiles) != len(faces):
        raise ValueError('Every Doll face must retain its material tile')
    joints, influences, parents = _skeleton(seed)
    joint_index = {name: i for i, name in enumerate(joints)}
    influence_slot = {int(joint): i for i, joint in enumerate(influences)}
    missing = sorted(set(model.bones) - joint_index.keys())
    if missing:
        raise ValueError(f'Doll bones are missing from the shipping skeleton: {missing}')
    used = np.array([influence_slot[joint_index[name]] for name in model.bones], dtype=np.uint16)

    normal = np.zeros_like(points)
    corners = points[faces]
    area = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    good = np.linalg.norm(area, axis=1) > 1.e-8
    for _, _, first, end, lo, hi in model.parts:
        local = np.zeros((hi - lo, 3), dtype=np.float32)
        for corner in range(3):
            np.add.at(local, faces[first:end, corner] - lo, area[first:end])
        _, inverse = np.unique(np.round(points[lo:hi], 5), axis=0, return_inverse=True)
        sums = np.zeros((int(inverse.max()) + 1, 3), dtype=np.float32)
        np.add.at(sums, inverse, local)
        normal[lo:hi] = sums[inverse]
    length = np.linalg.norm(normal, axis=1)
    normal /= np.maximum(length[:, None], 1.e-10)

    vertices = np.zeros(len(points), dtype=DT)
    vertices['p'] = points
    vertices['n'] = normal
    vertices['uv'] = np.asarray(model.uv, dtype=np.float32)
    vertices['i'][:, 0] = used
    vertices['w'][:, 0] = 1.
    unique, remap = np.unique(vertices, return_inverse=True)
    triangles = remap[faces[good]].astype('<u2')
    face_tiles = tiles[good]
    if len(unique) >= 65536:
        raise ValueError(f'Doll mesh exceeds the native 16-bit section limit: {len(unique)}')
    if not np.allclose(unique['w'].sum(1), 1., atol=1.e-6):
        raise ValueError('Doll vertex weights must sum to one')
    if int(unique['i'].max()) >= len(influences):
        raise ValueError('Doll vertex refers outside the SKL influence table')
    if np.any(np.linalg.norm(unique['n'], axis=1) < .98):
        raise ValueError('Doll contains an invalid or zero normal')
    return unique, triangles, face_tiles, joints, influences, parents


def section(seed):
    """Return the complete Doll section in the shipping SKN vertex layout."""
    vertices, triangles, *_ = _mesh(seed)
    return vertices, triangles


def authoring_data(seed, path=None):
    """Save source mesh arrays for Blender installation and exact parity checks."""
    atlas, _ = _load_sources()
    vertices, triangles, face_tiles, joints, influences, parents = _mesh(seed)
    path = Path(path or (PLUSH / 'build' / 'doll-polish-v2.npz'))
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, vertices=vertices, triangles=triangles,
                        face_tiles=face_tiles, names=np.asarray(joints, dtype='U48'),
                        influences=influences, parents=parents)
    return path


def _painted_atlas():
    atlas, _ = _load_sources()
    image = atlas.make_atlas()
    # Apply the same game-specific embroidered face and cloth finish used by the
    # shipping texture. Blender reads this exact PNG, so authoring and export match.
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    if str(GW / 'vfx') not in sys.path:
        sys.path.insert(0, str(GW / 'vfx'))
    if str(PLUSH) not in sys.path:
        sys.path.insert(0, str(PLUSH))
    spec = importlib.util.spec_from_file_location('_gwen_doll_paint', HERE / 'repair_paint.py')
    paint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(paint)
    image = paint.doll()
    image.save(atlas.ATLAS)
    return atlas, image


def _rma(atlas):
    image = Image.new('RGB', (atlas.SIZE, atlas.SIZE), (232, 0, 247))
    draw = ImageDraw.Draw(image)
    for name, (x, y, w, h) in atlas.RECT.items():
        # R, G, B are roughness, metallic response, and cavity/AO response.
        value = (232, 0, 247)
        if name == 'gold':
            value = (164, 12, 242)  # densely sewn metallic thread
        elif name in ('pink_gem', 'azure', 'pin_blue', 'pin_rose'):
            value = (105, 19, 240)  # polished satin jewel insets
        elif name == 'champagne':
            value = (128, 92, 242)  # champagne-gold pin setting
        elif name == 'sole':
            value = (190, 0, 238)   # soft leather soles
        elif name == 'ink':
            value = (214, 0, 245)   # matte embroidery and outlines
        elif name.startswith('face'):
            value = (246, 0, 250)   # cotton face, no plastic highlight
        elif name == 'badge':
            value = (230, 0, 248)
        draw.rectangle((x, y, x + w - 1, y + h - 1), fill=value)
    return image


def apply(assets, tmp, packed_diffuse=None):
    """Replace Doll diffuse/RMA resources with the matched high-resolution maps."""
    if str(GW / 'vfx') not in sys.path:
        sys.path.insert(0, str(GW / 'vfx'))
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    from diffuse_tex import encode as encode_diffuse
    if str(PLUSH) not in sys.path:
        sys.path.insert(0, str(PLUSH))
    from repair_paint import encode_particle, decode_full
    if packed_diffuse is None:
        atlas,diffuse=_painted_atlas()
    else:
        atlas,_=_load_sources()
        with Image.open(packed_diffuse) as packed:diffuse=packed.convert('RGB')
    source_diffuse = diffuse.convert('RGBA')
    diffuse_tex = encode_diffuse(source_diffuse)
    if not np.array_equal(np.asarray(decode_full(diffuse_tex)), np.asarray(source_diffuse)):
        raise ValueError('Lossless Doll diffuse round-trip changed source pixels')
    rma = _rma(atlas)
    source_rma = rma.convert('RGBA')
    rma_tex = encode_particle(source_rma)
    if not np.array_equal(np.asarray(decode_full(rma_tex)), np.asarray(source_rma)):
        raise ValueError('Lossless Doll RMA round-trip changed source pixels')
    assets[TEXTURE] = diffuse_tex
    assets[DOLL_RMA] = rma_tex
    tmp = Path(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    diffuse.save(tmp / 'doll-polish-diffuse.png')
    rma.save(tmp / 'doll-polish-rma.png')
    return assets

