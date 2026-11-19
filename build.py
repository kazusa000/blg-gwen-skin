"""Build the complete Gwen skin from the Blender master on Windows."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source/Gwen1'
RECALL = SOURCE / 'recall'
MASTER = ROOT / 'skin/Gwen1/Gwen1-BLG.blend'
WORK = RECALL / 'build/full-source'
sys.path.insert(0, str(SOURCE / 'vfx'))
from build_qw import DEFAULT_GAME, convert


def prepare():
    stock = SOURCE / 'rig-study'
    stock.mkdir(exist_ok=True)
    wad = DEFAULT_GAME / 'DATA/FINAL/Champions/Gwen.wad.client'
    for path, filename in [
        ('assets/characters/gwen/skins/base/gwen_base.skn', 'gwen_base.skn'),
        ('assets/characters/gwen/skins/base/gwen_base.skl', 'gwen_base.skl'),
        ('assets/characters/gwen/skins/base/animations/idle.anm', 'idle.anm'),
        ('assets/characters/gwen/skins/base/animations/joke_start.anm', 'joke_start.anm'),
        ('assets/characters/gwen/skins/base/animations/attack1.anm', 'attack1.anm'),
        ('data/characters/gwen/skins/skin0.bin', 'skin0.bin'),
        ('data/characters/gwen/animations/skin0.bin', 'animation-skin0.bin'),
    ]:
        subprocess.run(['node', RECALL/'game_wad.cjs', wad, path, stock/filename], check=True)
    convert(stock/'skin0.bin', stock/'skin0_named.rito')
    convert(stock/'animation-skin0.bin', stock/'animation-skin0_named.rito')
    shutil.copyfile(stock/'animation-skin0_named.rito', stock/'animation-skin0.rito')
    for family in ('face', 'pile'):
        shutil.copytree(SOURCE/'inputs/projections'/family, WORK/family, dirs_exist_ok=True)


def blender(script, *options):
    exe = os.environ.get('GWEN_BLENDER', 'blender')
    subprocess.run([exe, '--background', '--factory-startup', '--disable-autoexec',
                    MASTER, '--python-exit-code', '1', '--python', RECALL/script, '--', *options], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['all', 'prepare', 'capture', 'export', 'paint', 'package'], default='all')
    stage = parser.parse_args().stage
    if stage in ('all', 'prepare'):
        prepare()
    if stage == 'capture':
        for family in ('face', 'pile'):
            blender('fidelity_capture.py', family+'-hd')
    if stage in ('all', 'export'):
        if not MASTER.is_file():
            raise SystemExit(f'Blender master missing: {MASTER}')
        blender('source_geometry.py')
    if stage in ('all', 'paint'):
        for script in ('source_paint.py', 'source_materials.py'):
            subprocess.run([sys.executable, RECALL/script], check=True)
    if stage in ('all', 'package'):
        subprocess.run([sys.executable, RECALL/'source_package.py'], check=True)


if __name__ == '__main__':
    main()
