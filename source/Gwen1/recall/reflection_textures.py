"""Bake native masked highlights from the authored roughness/metallic/occlusion maps."""
import numpy as np
from PIL import Image
from repair_paint import decode_full, encode_particle
from native_materials import BODY_REFLECTION, WEAPON_REFLECTION, REFLECTION_LIGHT


def strength(rma):
    roughness, metal, occlusion = np.moveaxis(rma, -1, 0)
    return .45 * (1-roughness)**1.8 * (.37+.63*metal) * occlusion

def reflection_mask(raw):
    source = decode_full(raw).convert('RGB')
    mask = Image.new('L', source.size)
    for y in range(0, source.height, 128):
        region = source.crop((0,y,source.width,min(y+128,source.height)))
        weight = strength(np.asarray(region, dtype=np.float32)/255)
        mask.paste(Image.fromarray(np.uint8(np.rint(255*weight))), (0,y))
    return encode_particle(mask.convert('RGBA'))


def reflection_textures(folder):
    assets = {}
    for target, filename in ((BODY_REFLECTION, 'surface-rma.tex'), (WEAPON_REFLECTION, 'weapon-rma.tex')):
        assets[target] = reflection_mask((folder/filename).read_bytes())
    # Small, softly edged studio lights sampled with the native view-space normals.
    axis = (np.arange(256)+.5)/128-1
    x,y = np.meshgrid(axis,axis)
    key = np.exp(-((x+.43+.26*y)/.19)**2-((y+.31)/.66)**2)
    fill = np.exp(-((x-.48+.24*y)/.30)**2-((y-.08)/.52)**2)
    light = .014 + key[:,:,None]*np.array([.86,.83,.82]) + fill[:,:,None]*np.array([.32,.37,.43])
    assets[REFLECTION_LIGHT] = encode_particle(Image.fromarray(np.uint8(np.rint(255*light))).convert('RGBA'))
    return assets
