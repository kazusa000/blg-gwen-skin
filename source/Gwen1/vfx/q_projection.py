"""Export the review camera and blade separation to align the native Q cast meshes."""
import json
from pathlib import Path
import sys
import bpy
import numpy as np

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here))
import preview_skills as preview

scene = bpy.context.scene
rig = scene.objects['BLG Gwen · Skin0']
camera = scene.objects[preview.CAMERA]
timeline = preview.q_frames()
scene.render.resolution_x, scene.render.resolution_y = 620, 560
preview.fit_q_camera(scene, rig, camera, timeline)
scene.frame_set(timeline[0][0])
deps = bpy.context.evaluated_depsgraph_get()
projection = camera.calc_matrix_camera(deps, x=620, y=560) @ camera.matrix_world.inverted()
records = []
for frame, stage, tick in timeline:
    scene.frame_set(frame)
    a = preview.blade_tip(scene, rig, scene.objects['Azure · ground crystal blade'], 'A')
    b = preview.blade_tip(scene, rig, scene.objects['Rose · ground crystal blade'], 'B')
    ground = rig.matrix_world @ rig.pose.bones['Buffbone_Glb_Ground_Loc'].matrix.translation
    records.append(dict(stage=stage, tick=tick, separation=(a-b).length,
                        ground=list(ground), tip=list((a+b)*.5)))
(here/'build'/'q-camera.json').write_text(json.dumps(dict(matrix=np.array(projection).tolist(), frames=records)))
