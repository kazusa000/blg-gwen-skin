"""Build the shared Blender/native 2233 Doll source artifacts outside Blender."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from core import HERE
from doll_polish import DOLL_RMA, TEXTURE, apply, authoring_data, section

GW = HERE.parent
PLUSH = GW / 'plush_2233'
SEED = HERE / 'gameplay-resources.zip'
OUT = PLUSH / 'build'
OUT.mkdir(parents=True, exist_ok=True)

assets = {}
with ZipFile(SEED) as seed:
    vertices, triangles = section(seed)
    apply(assets, OUT)
    npz = authoring_data(seed, OUT / 'doll-polish-v2.npz')

diffuse_path = OUT / 'doll-polish-diffuse.tex'
rma_path = OUT / 'doll-polish-rma.tex'
diffuse_path.write_bytes(assets[TEXTURE])
rma_path.write_bytes(assets[DOLL_RMA])
report = {
    'source': str(npz),
    'diffuse': {'path': str(diffuse_path), 'sha256': hashlib.sha256(assets[TEXTURE]).hexdigest(),
                'width': 4096, 'format': 'lossless RGBA8 with mips'},
    'rma': {'path': str(rma_path), 'sha256': hashlib.sha256(assets[DOLL_RMA]).hexdigest(),
            'width': 4096, 'format': 'lossless RGBA8 with mips'},
    'vertices': len(vertices), 'triangles': len(triangles),
    'section_sha256': hashlib.sha256(vertices.tobytes() + triangles.tobytes()).hexdigest(),
}
(OUT / 'doll-polish-report.json').write_text(json.dumps(report, indent=2), 'utf8')
print(json.dumps(report, indent=2), flush=True)
