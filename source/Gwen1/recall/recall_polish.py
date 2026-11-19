"""Speed up the four banner cuts and bind their flashes in the game BINs.

The pass is additive: it only appends recall flash systems/events and retimes the
recall ANM. Existing combat aliases, systems, and graph nodes remain untouched.
"""
from __future__ import annotations

import re
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
GW = HERE.parent
ROOT = "assets/characters/gwen/skins/base/"
SKIN_BIN = "data/characters/gwen/skins/skin0.bin"
ANIM_BIN = "data/characters/gwen/animations/skin0.bin"
SKL_PATH = ROOT + "gwen_base.skl"
ANM_PATH = ROOT + "animations/recall.anm"
STAR_TEX = ROOT + "particles/blg_qw/q_final_star.tex"

MAIN = 0xFB3D5213  # Recall1

# The cut closes move from 32/59/86/116 to 26/47/68/89. The trophy seat
# exchange moves from 142 to 122; the 194-frame doll swap and 240-frame end stay.
OLD_CUTS = (32, 59, 86, 116)
NEW_CUTS = (26, 47, 68, 89)
OLD_BLINKS = (20, 46, 74, 104)
NEW_BLINKS = (16, 37, 59, 81)
OLD_SEAT = 142
NEW_SEAT = 122
SWAP = 194
LAST = 240
RETIME_SRC = (0, 19, 20, 32, 45, 46, 59, 73, 74, 86, 103, 104,
              116, 141, 142, 194, 240)
RETIME_DST = (0, 15, 16, 26, 36, 37, 47, 58, 59, 68, 80, 81,
              89, 121, 122, 194, 240)

sys.path.insert(0, str(GW))
sys.path.insert(0, str(GW / "vfx"))
from build_qw import convert
from core import fmt_key, compose  # noqa: E402
from q_effect import _entries, _matching_brace, _top_level_resource  # noqa: E402
from rig_data import decode_quat  # noqa: E402


def _hash(name: str) -> int:
    return int(fmt_key(name), 16)


def _joint_hash(name: str) -> int:
    value = 0
    for byte in name.lower().encode("utf-8"):
        value = value * 16 + byte
        high = value & 0xF0000000
        value = (value ^ (high >> 24)) & ~high
    return value


def _map_old_frame(frame: float) -> float:
    return float(np.interp(frame, RETIME_SRC, RETIME_DST))


def _convert(source: Path, dest: Path) -> None:
    convert(source, dest)


def _binary_entries(data: bytes):
    if data[:8] != b"PROP\x03\x00\x00\x00":
        raise ValueError("Expected a PROP v3 BIN resource")
    at = 12
    for _ in range(struct.unpack_from("<I", data, 8)[0]):
        at += 2 + struct.unpack_from("<H", data, at)[0]
    header = data[:at]
    count = struct.unpack_from("<I", data, at)[0]
    at += 4
    types = struct.unpack_from(f"<{count}I", data, at)
    at += 4 * count
    rows = {}
    for kind in types:
        size, key = struct.unpack_from("<II", data, at)
        if key in rows:
            raise ValueError(f"Duplicate BIN object 0x{key:08x}")
        rows[key] = (kind, data[at:at + size + 4])
        at += size + 4
    if at != len(data):
        raise ValueError("Trailing bytes in PROP resource")
    return header, rows


def _keep_untouched(original: bytes, compiled: bytes, changed: set[int]) -> bytes:
    head, old = _binary_entries(original)
    new_head, new = _binary_entries(compiled)
    if head != new_head or not set(old) <= set(new):
        raise ValueError("Ritobin compile changed the resource header/object set")
    rows = [new[key] if key in changed or key not in old else old[key] for key in new]
    return (head + struct.pack("<I", len(rows)) +
            b"".join(struct.pack("<I", kind) for kind, _ in rows) +
            b"".join(blob for _, blob in rows))


def _parse_anm(data: bytes):
    if data[:8] != b"r3d2anmd" or struct.unpack_from("<I", data, 8)[0] != 5:
        raise ValueError("Expected the recall animation in dense ANM v5 format")
    n, f, dt, hash_rel = struct.unpack_from("<IIfI", data, 28)
    vec_rel, quat_rel, frame_rel = struct.unpack_from("<III", data, 52)
    vec_at, quat_at, hashes_at = 12 + vec_rel, 12 + quat_rel, 12 + hash_rel
    frame_at = 12 + frame_rel
    if f != LAST + 1 or n < 180 or frame_at + f * n * 6 != len(data):
        raise ValueError(f"Unexpected recall ANM dimensions: {f} frames / {n} joints")
    vec_count = (quat_at - vec_at) // 12
    quat_count = (hashes_at - quat_at) // 6
    vectors = np.frombuffer(data, "<f4", vec_count * 3, vec_at).reshape(-1, 3)
    qpacked = np.frombuffer(data, "<u2", quat_count * 3, quat_at).reshape(-1, 3)
    hashes = np.frombuffer(data, "<u4", n, hashes_at).copy()
    indices = np.frombuffer(data, "<u2", f * n * 3, frame_at).reshape(f, n, 3)
    positions = vectors[indices[:, :, 0]].copy()
    scales = vectors[indices[:, :, 1]].copy()
    rotations = decode_quat(qpacked[indices[:, :, 2]]).copy()
    return data[:76], hashes, positions, scales, rotations, float(dt)


def _source_frame(frame: float) -> float:
    # Compress the four snip beats; stage the trophy 20 frames sooner; keep the
    # doll swap and final wave on their approved game frames.
    return float(np.interp(frame, RETIME_DST, RETIME_SRC))


def _resample(values: np.ndarray, frame_map: np.ndarray) -> np.ndarray:
    lo = np.floor(frame_map).astype(int)
    hi = np.minimum(lo + 1, len(values) - 1)
    t = (frame_map - lo).reshape((-1,) + (1,) * (values.ndim - 1))
    return values[lo] * (1 - t) + values[hi] * t


def _retime_anm(data: bytes) -> tuple[bytes, dict[str, float]]:
    header, hashes, pos, scale, quat, dt = _parse_anm(data)
    fmap = np.array([_source_frame(float(i)) for i in range(LAST + 1)])
    new_pos = _resample(pos, fmap).astype(np.float32)
    new_scale = _resample(scale, fmap).astype(np.float32)
    lo = np.floor(fmap).astype(int)
    hi = np.minimum(lo + 1, len(quat) - 1)
    amount = (fmap - lo)[:, None, None]
    q0, q1 = quat[lo], quat[hi]
    q1 = q1 * np.where((q0 * q1).sum(axis=-1, keepdims=True) < 0, -1, 1)
    new_quat = (q0 * (1 - amount) + q1 * amount).astype(np.float32)
    new_quat /= np.maximum(np.linalg.norm(new_quat, axis=-1, keepdims=True), 1e-10)
    if (np.max(np.abs(new_pos[SWAP:] - pos[SWAP:])) > .015 or
            np.max(np.abs(new_scale[SWAP:] - scale[SWAP:])) > .015 or
            np.max(1 - np.abs(np.sum(new_quat[SWAP:] * quat[SWAP:], axis=-1))) > .001):
        raise AssertionError("Trophy/doll swap and end-wave poses must remain unchanged")

    frame_count, joint_count = new_pos.shape[:2]
    v, vi = np.unique(np.round(np.stack((new_pos, new_scale), axis=-2)
                               .reshape(-1, 3), 5).astype("<f4"), axis=0,
                      return_inverse=True)
    vi = vi.reshape(frame_count, joint_count, 2)
    omit = np.argmax(np.abs(new_quat), axis=-1)
    sign = np.take_along_axis(new_quat, omit[..., None], axis=-1)[..., 0]
    q = new_quat * np.where(sign < 0, -1, 1)[..., None]
    three = q[np.arange(4) != omit[..., None]].reshape(frame_count, joint_count, 3)
    enc = np.rint((three + 1 / np.sqrt(2)) * 32767 / np.sqrt(2))
    enc = enc.clip(0, 32767).astype("u8")
    bits = ((omit.astype("u8") << 45) | (enc[..., 0] << 30) |
            (enc[..., 1] << 15) | enc[..., 2])
    unique_q, qi = np.unique(bits, return_inverse=True)
    if len(v) >= 65536 or len(unique_q) >= 65536:
        raise ValueError("ANM retime exceeded the v5 dictionary capacity")
    qbytes = np.stack([(unique_q >> (16 * i)) & 65535 for i in range(3)],
                      axis=-1).astype("<u2").tobytes()
    indices = np.concatenate((vi, qi.reshape(frame_count, joint_count, 1)), axis=-1)
    body = (v.tobytes() + qbytes + hashes.astype("<u4").tobytes() +
            indices.astype("<u2").tobytes())
    out = bytearray(header)
    vo = len(out)
    qo = vo + v.nbytes
    ho = qo + len(qbytes)
    fo = ho + 4 * joint_count
    out.extend(body)
    struct.pack_into("<I", out, 12, len(out) - 12)
    struct.pack_into("<IIfI", out, 28, joint_count, frame_count, dt, ho - 12)
    struct.pack_into("<III", out, 52, vo - 12, qo - 12, fo - 12)
    info = {"duration_frames": frame_count - 1, "joints": joint_count,
            "blink_frames": NEW_BLINKS, "cut_frames": NEW_CUTS,
            "seat_frame": NEW_SEAT, "swap_frame": SWAP,
            "wave_end_frame": LAST}
    return bytes(out), info


def _color(alpha: tuple[float, ...]) -> str:
    times = (0, .12, .72, 1)
    values = ((.12, .66, 1, 0), (1, 1, 1, alpha[0]),
              (1, 1, 1, alpha[1]), (1, .25, .70, 0))
    rows = "\n".join(f"                            {{ {r}, {g}, {b}, {a} }}"
                     for r, g, b, a in values)
    return f'''embed = ValueColor {{
                    dynamics: pointer = VfxAnimatedColorVariableData {{
                        times: list[f32] = {{ {', '.join(map(str, times))} }}
                        values: list[vec4] = {{
{rows}
                        }}
                    }}
                }}'''


def _emitter(name: str, size: float, life: float, delay: float, tint_peak: float) -> str:
    return f'''            VfxEmitterDefinitionData {{
                emitterName: string = "{name}"
                timeBeforeFirstEmission: f32 = {delay}
                isSingleParticle: flag = true
                particleLinger: option[f32] = {{ 0 }}
                emitterLinger: option[f32] = {{ 0 }}
                rate: embed = ValueFloat {{ constantValue: f32 = 1 }}
                lifetime: option[f32] = {{ {life} }}
                particleLifetime: embed = ValueFloat {{ constantValue: f32 = {life} }}
                bindWeight: embed = ValueFloat {{ constantValue: f32 = 1 }}
                EmitterPosition: embed = ValueVector3 {{ constantValue: vec3 = {{ 0, 0, 0 }} }}
                birthVelocity: embed = ValueVector3 {{ constantValue: vec3 = {{ 0, 56, 0 }} }}
                birthScale0: embed = ValueVector3 {{ constantValue: vec3 = {{ {size}, {size}, 1 }} }}
                isRotationEnabled: flag = true
                birthRotation0: embed = ValueVector3 {{ constantValue: vec3 = {{ 0, 0, 0 }} }}
                birthRotationalVelocity0: embed = ValueVector3 {{ constantValue: vec3 = {{ 0, 0, 0 }} }}
                isLocalOrientation: flag = false
                Color: { _color((tint_peak, tint_peak * .78)) }
                blendMode: u8 = 4
                pass: i16 = 72
                texture: string = "{STAR_TEX}"
            }}'''


def _system(name: str, size: float) -> tuple[int, str]:
    path = "Characters/Gwen/Skins/Skin0/Particles/" + name
    object_hash = _hash(path)
    emitters = "\n".join((
        _emitter(name + "_GemFlash", size, .22, 0, 1),
        _emitter(name + "_RoseFacet", size * .58, .18, .018, .82),
    ))
    block = f'''    0x{object_hash:08x} = VfxSystemDefinitionData {{
        complexEmitterDefinitionData: list[pointer] = {{
{emitters}
        }}
        visibilityRadius: f32 = 540
        particleName: string = "{name}"
        particlePath: string = "{path}"
        objectPath: hash = 0x{object_hash:08x}
    }}'''
    return object_hash, block


def _event(key_name: str, alias: int, bone: str, frame: int, end: int) -> str:
    event_key = _hash(key_name)
    return f'''                    0x{event_key:08x} = ParticleEventData {{
                        mStartFrame: f32 = {frame}
                        mEndFrame: f32 = {end}
                        mEffectKey: hash = 0x{alias:08x}
                        mParticleEventDataPairList: list[embed] = {{
                            ParticleEventDataPair {{ mBoneName: hash = {fmt_key(bone)} }}
                        }}
                        mScalePlaySpeedWithAnimation: bool = true
                    }}'''


def _add_systems(data: bytes, tmp: Path) -> bytes:
    src, rito, dst = tmp / "recall-skin0.bin", tmp / "recall-skin0.rito", tmp / "recall-skin0-new.bin"
    src.write_bytes(data)
    _convert(src, rito)
    text = rito.read_text(encoding="utf-8")
    prefix, records, suffix = _entries(text)
    hashes = {k for k, _, _ in records}
    resolver_key, resolver = next(((k, b) for k, kind, b in records if kind == "ResourceResolver"), (None, None))
    if resolver is None:
        raise ValueError("Gwen skin BIN has no ResourceResolver")
    mapped = {int(alias, 16): int(target, 16)
              for alias, target in re.findall(r"0x([0-9a-fA-F]+)\s*=\s*0x([0-9a-fA-F]+)", resolver)}
    departure_object = _hash("Characters/Gwen/Skins/Skin0/Particles/BLG_Recall_Flash_Departure")
    change_object = _hash("Characters/Gwen/Skins/Skin0/Particles/BLG_Recall_Flash_Change")
    old_departure_alias = next((alias for alias, target in mapped.items() if target == departure_object), None)
    old_change_alias = next((alias for alias, target in mapped.items() if target == change_object), None)
    if old_departure_alias is None or old_change_alias is None:
        raise ValueError("Seed resolver is missing the exported recall departure/change aliases")
    aliases = {"Arrival": _hash("BLG_Recall_ArrivalFlash_Event"),
               "Snip": _hash("BLG_Recall_SnipFlash_Event")}

    updates = {}
    specs = (("BLG_Recall_Flash_Departure", 156),
             ("BLG_Recall_Flash_Change", 166),
             ("BLG_Recall_Flash_Arrival", 152),
             ("BLG_Recall_Flash_Snip", 124))
    for name, size in specs:
        object_hash, block = _system(name, size)
        if name.endswith("Departure") or name.endswith("Change"):
            if object_hash not in hashes:
                raise ValueError(f"Seed is missing its existing recall flash system: {name}")
            updates[object_hash] = block
        elif object_hash in hashes:
            updates[object_hash] = block
        else:
            updates[object_hash] = block
            hashes.add(object_hash)

    # Keep the shipped aliases for the two existing flash systems. Add only the
    # arrival and flag-snip aliases; this composes with combat additions.
    added_aliases = []
    for label in ("Arrival", "Snip"):
        alias = aliases[label]
        if alias not in mapped:
            name = "BLG_Recall_Flash_" + label
            added_aliases.append((alias, _hash("Characters/Gwen/Skins/Skin0/Particles/" + name)))
    if added_aliases:
        start, end = _top_level_resource(resolver)
        field = resolver[start:end]
        field = field[:-1] + "\n" + "\n".join(f"            0x{a:08x} = 0x{o:08x}" for a, o in added_aliases) + "\n        }"
        resolver = resolver[:start] + field + resolver[end:]
    records = [(k, kind, resolver if k == resolver_key else updates.get(k, b))
               for k, kind, b in records]
    present = {k for k, _, _ in records}
    for key, block in updates.items():
        if key not in present:
            records.append((key, "VfxSystemDefinitionData", block))
    edited = prefix + "\n" + "\n".join(b for _, _, b in records) + "\n" + suffix
    rito.write_text(edited, encoding="utf-8")
    _convert(rito, dst)
    return _keep_untouched(data, dst.read_bytes(), {resolver_key, *updates.keys()})


def _add_events(data: bytes, tmp: Path) -> bytes:
    src, rito, dst = tmp / "recall-anim0.bin", tmp / "recall-anim0.rito", tmp / "recall-anim0-new.bin"
    src.write_bytes(data)
    _convert(src, rito)
    text = rito.read_text(encoding="utf-8")
    prefix, records, suffix = _entries(text)
    rows = []
    changed = set()
    found_main = False
    aliases = {"Arrival": _hash("BLG_Recall_ArrivalFlash_Event"),
               "Snip": _hash("BLG_Recall_SnipFlash_Event")}
    for key, kind, block in records:
        if kind == "AnimationGraphData":
            graph = block
            clip_start_match = re.search(r"(?m)^\s*0x" + f"{MAIN:08x}" + r" = AtomicClipData \{", graph)
            if not clip_start_match:
                rows.append((key, kind, block))
                continue
            found_main = True
            clip_start = clip_start_match.start()
            clip_open = graph.find("{", clip_start_match.start(), clip_start_match.end())
            clip_end = _matching_brace(graph, clip_open)
            clip = graph[clip_start:clip_end]
            if f"0x{_hash('BLG_Recall_Snip_0'):08x} = ParticleEventData" in clip:
                rows.append((key, kind, block))
                return data
            event_match = re.search(r"(?m)^\s*mEventDataMap: map\[hash, pointer\] = \{", clip)
            if not event_match:
                raise ValueError("Recall1 clip is missing its event map")
            event_open = clip.find("{", event_match.start(), event_match.end())
            event_end = _matching_brace(clip, event_open)
            events = []
            new_event_keys = set()
            for i, frame in enumerate(NEW_BLINKS):
                name = f"BLG_Recall_Arrival_{i}"
                events.append(_event(name, aliases["Arrival"], "Root", frame, frame + 1))
                new_event_keys.add(_hash(name))
            name = "BLG_Recall_Arrival_Seat"
            events.append(_event(name, aliases["Arrival"], "Root", NEW_SEAT, NEW_SEAT + 1))
            new_event_keys.add(_hash(name))
            for i, frame in enumerate(NEW_CUTS):
                name = f"BLG_Recall_Snip_{i}"
                events.append(_event(name, aliases["Snip"], f"RC_Burst{i}", frame, frame + 1))
                new_event_keys.add(_hash(name))
            event_map = clip[event_match.start():event_end]
            event_map = event_map[:-1] + "\n" + "\n".join(events) + "\n                }"
            clip = clip[:event_match.start()] + event_map + clip[event_end:]

            # The seed already has five departure, five hide, and two transition
            # events. Retarget their frame windows in place so no old-frame flash
            # is left behind when the retimed ANM is played.
            event_match = re.search(r"(?m)^\s*mEventDataMap: map\[hash, pointer\] = \{", clip)
            event_open = clip.find("{", event_match.start(), event_match.end())
            event_end = _matching_brace(clip, event_open)
            event_map = clip[event_match.start():event_end]
            patterns = list(re.finditer(r"(?m)^\s*(0x[0-9a-fA-F]+) = (\w+) \{", event_map))
            for match in reversed(patterns):
                if int(match.group(1), 16) in new_event_keys:
                    continue
                row_open = event_map.find("{", match.start(), match.end())
                row_end = _matching_brace(event_map, row_open)
                row = event_map[match.start():row_end]
                if match.group(2) in ("SubmeshVisibilityEventData", "ParticleEventData"):
                    if match.group(2) == "ParticleEventData" and _event_alias(row) == 0xDD7769A6:
                        start, end = _event_number(row, "mStartFrame"), _event_number(row, "mEndFrame")
                        center = (start + end) / 2 if start is not None and end is not None else 0
                        old_blinks = (*OLD_BLINKS, OLD_SEAT)
                        new_blinks = (*NEW_BLINKS, NEW_SEAT)
                        index = int(np.argmin(np.abs(np.asarray(old_blinks, dtype=float) - center)))
                        new_start = new_blinks[index]
                        for field, value in (("mStartFrame", new_start), ("mEndFrame", new_start + 1)):
                            row = re.sub(r"(?m)(" + field + r": f32 = )(-?[0-9.]+)",
                                         lambda m, v=value: m.group(1) + str(v), row, count=1)
                    else:
                        for field in ("mStartFrame", "mEndFrame"):
                            row = re.sub(r"(?m)(" + field + r": f32 = )(-?[0-9.]+)",
                                         lambda m: m.group(1) + str(int(round(_map_old_frame(float(m.group(2)))))),
                                         row, count=1)
                event_map = event_map[:match.start()] + row + event_map[row_end:]
            clip = clip[:event_match.start()] + event_map + clip[event_end:]
            graph = graph[:clip_start] + clip + graph[clip_end:]
            block = graph
            changed.add(key)
        rows.append((key, kind, block))
    if not found_main:
        raise ValueError("Recall1 clip is missing from the animation graph")
    edited = prefix + "\n" + "\n".join(b for _, _, b in rows) + "\n" + suffix
    rito.write_text(edited, encoding="utf-8")
    _convert(rito, dst)
    return _keep_untouched(data, dst.read_bytes(), changed)


def _skeleton_joints(blob: bytes):
    if struct.unpack_from("<II", blob, 4) != (0x22FD4FC3, 0):
        raise ValueError("Expected Gwen's exported SKL")
    count, _, joints_at, _, _ = struct.unpack_from("<HIIII", blob, 14)
    rows = []
    for index in range(count):
        at = joints_at + index * 100
        joint_index, parent, hash_value = struct.unpack_from("<Hh2xI", blob, at + 2)
        if joint_index != index:
            raise ValueError("SKL joint table index is not sequential")
        name_at = at + 96 + struct.unpack_from("<i", blob, at + 96)[0]
        name_end = blob.index(0, name_at)
        rows.append((blob[name_at:name_end].decode("utf-8"), int(hash_value), int(parent)))
    return rows


def _check_anm(blob: bytes, skl_blob: bytes) -> dict:
    _, hashes, pos, scale, quat, dt = _parse_anm(blob)
    ids = {int(h): i for i, h in enumerate(hashes)}
    joints = _skeleton_joints(skl_blob)
    skl_by_name = {name: (joint_hash, parent) for name, joint_hash, parent in joints}
    required_names = ["Root", *(f"RC_Dash{i}" for i in range(4)),
                      *(f"RC_Burst{i}" for i in range(4))]
    for name in required_names:
        if name not in skl_by_name or skl_by_name[name][0] != _joint_hash(name):
            raise ValueError(f"Exported SKL does not contain the expected joint {name}")
    parents = np.full(len(hashes), -1, dtype=int)
    for _, joint_hash, parent in joints:
        if joint_hash not in ids:
            raise ValueError("Recall animation and exported SKL joint sets differ")
        if parent >= 0:
            parents[ids[joint_hash]] = ids[joints[parent][1]]
    local = compose(pos.astype(float), scale.astype(float), quat.astype(float))
    world = local.copy()
    for _, joint_hash, parent in joints:
        child = ids[joint_hash]
        if parent >= 0:
            world[:, child] = world[:, parents[child]] @ local[:, child]
    # Dash nodes are authored at the old location; Root is already at the new
    # location on the same frame. Both values are measured after SKL parenting.
    points = {}
    blink_specs = [*( (i, frame) for i, frame in enumerate(NEW_BLINKS) ), (4, NEW_SEAT)]
    for i, frame in blink_specs:
        dash_i = min(i, 3)
        d = world[frame, ids[_joint_hash("RC_Dash" + str(dash_i))], :3, 3]
        r = world[frame, ids[_joint_hash("Root")], :3, 3]
        points[f"blink_{i}"] = {"frame": frame, "departure_bone": f"RC_Dash{dash_i}",
                                "arrival_bone": "Root", "departure": d.tolist(), "arrival": r.tolist(),
                                "separation": float(np.linalg.norm(d - r))}
    for i, frame in enumerate(NEW_CUTS):
        points[f"snip_{i}"] = {"burst": world[frame, ids[_joint_hash("RC_Burst" + str(i))], :3, 3].tolist()}
    change_hash = _joint_hash("RC_Change")
    if change_hash not in ids:
        raise ValueError("Recall ANM is missing the trophy/doll transition joint")
    change_joint = ids[change_hash]
    points["change_seat"] = world[NEW_SEAT, change_joint, :3, 3].tolist()
    points["change_doll"] = world[SWAP, change_joint, :3, 3].tolist()
    feet = [ids[_joint_hash(name)] for name in ("L_Foot", "R_Foot") if _joint_hash(name) in ids]
    if not feet:
        raise ValueError("Recall ANM is missing the native lower-leg joints")
    leg_translation = float(np.max(np.linalg.norm(pos[NEW_SEAT:SWAP + 1, feet] - pos[NEW_SEAT, feet], axis=-1)))
    leg_rotation = float(np.max(1 - np.abs(np.sum(quat[NEW_SEAT:SWAP + 1, feet] * quat[NEW_SEAT, feet], axis=-1))))
    points["seat"] = {"frame": NEW_SEAT, "dt_seconds": dt,
                      "leg_translation_peak": leg_translation,
                      "leg_rotation_peak": leg_rotation,
                      "legs_still_animated": leg_translation > .02 or leg_rotation > .001}
    points["wave"] = {"start": SWAP, "end": len(pos) - 1,
                      "duration_seconds": (len(pos) - 1 - SWAP) * dt}
    points["duration_seconds"] = (len(pos) - 1) * dt
    points["animation_joint_count"] = len(hashes)
    return points


def _has_events(data: bytes, tmp: Path) -> bool:
    src, rito = tmp / "recall-event-check.bin", tmp / "recall-event-check.rito"
    src.write_bytes(data)
    _convert(src, rito)
    _, records, _ = _entries(rito.read_text(encoding="utf-8"))
    graph = next((block for _, kind, block in records if kind == "AnimationGraphData"), "")
    return f"0x{_hash('BLG_Recall_Snip_0'):08x} = ParticleEventData" in graph


def _ritobin(data: bytes, tmp: Path, stem: str):
    src, rito = tmp / f"{stem}.bin", tmp / f"{stem}.rito"
    src.write_bytes(data)
    _convert(src, rito)
    return _entries(rito.read_text(encoding="utf-8"))


def _clip_events(data: bytes, tmp: Path):
    _, records, _ = _ritobin(data, tmp, "recall-event-readback")
    graph = next((block for _, kind, block in records if kind == "AnimationGraphData"), None)
    if graph is None:
        raise ValueError("Animation BIN has no AnimationGraphData")
    marker = re.search(r"(?m)^\s*0x" + f"{MAIN:08x}" + r" = AtomicClipData \{", graph)
    if marker is None:
        raise ValueError("AnimationGraphData does not contain Recall1")
    clip_end = _matching_brace(graph, graph.find("{", marker.start(), marker.end()))
    clip = graph[marker.start():clip_end]
    event_map_match = re.search(r"(?m)^\s*mEventDataMap: map\[hash, pointer\] = \{", clip)
    event_map_end = _matching_brace(clip, clip.find("{", event_map_match.start(), event_map_match.end()))
    event_map = clip[event_map_match.start():event_map_end]
    rows = []
    for match in re.finditer(r"(?m)^\s*(0x[0-9a-fA-F]+) = (\w+) \{", event_map):
        end = _matching_brace(event_map, event_map.find("{", match.start(), match.end()))
        rows.append((int(match.group(1), 16), match.group(2), event_map[match.start():end]))
    return rows


def _event_number(block: str, name: str):
    m = re.search(r"(?m)\b" + re.escape(name) + r": f32 = (-?[0-9.]+)", block)
    return None if m is None else int(round(float(m.group(1))))


def _event_alias(block: str):
    m = re.search(r"(?m)\bmEffectKey: hash = (0x[0-9a-fA-F]+)", block)
    return None if m is None else int(m.group(1), 16)


def _event_bone(block: str):
    m = re.search(r"(?m)\bmBoneName: hash = (0x[0-9a-fA-F]+)", block)
    return None if m is None else int(m.group(1), 16)


def _validate_bin_output(skin_blob: bytes, anim_blob: bytes, skl_blob: bytes, tmp: Path) -> dict:
    _, skin_rows, _ = _ritobin(skin_blob, tmp, "recall-skin-readback")
    objects = {key: (kind, block) for key, kind, block in skin_rows}
    resolver = next((block for _, kind, block in skin_rows if kind == "ResourceResolver"), None)
    if resolver is None:
        raise ValueError("Polished skin BIN lost its ResourceResolver")
    mappings = {int(a, 16): int(b, 16) for a, b in
                re.findall(r"0x([0-9a-fA-F]+)\s*=\s*0x([0-9a-fA-F]+)", resolver)}
    old_depart_obj = _hash("Characters/Gwen/Skins/Skin0/Particles/BLG_Recall_Flash_Departure")
    old_change_obj = _hash("Characters/Gwen/Skins/Skin0/Particles/BLG_Recall_Flash_Change")
    if mappings.get(0xDD7769A6) != old_depart_obj or mappings.get(0xEBFF97C2) != old_change_obj:
        raise ValueError("Existing departure/change aliases were not preserved")
    systems = {}
    for _, (kind, block) in objects.items():
        name = re.search(r'(?m)^\s*particleName: string = "([^"]+)"', block)
        if kind == "VfxSystemDefinitionData" and name:
            systems[name.group(1)] = block
    for name in ("BLG_Recall_Flash_Departure", "BLG_Recall_Flash_Change",
                 "BLG_Recall_Flash_Arrival", "BLG_Recall_Flash_Snip"):
        block = systems.get(name)
        if block is None or block.count("texture: string = \"" + STAR_TEX + "\"") < 2:
            raise ValueError(f"Four-point star flash system did not compile: {name}")
    joint_names = {name for name, _, _ in _skeleton_joints(skl_blob)}
    if not {"Root", *(f"RC_Dash{i}" for i in range(4)), *(f"RC_Burst{i}" for i in range(4))} <= joint_names:
        raise ValueError("Flash event names do not match the shipped SKL")
    events = _clip_events(anim_blob, tmp)
    dep = [e for _, k, e in events if k == "ParticleEventData" and _event_alias(e) == 0xDD7769A6]
    change = [e for _, k, e in events if k == "ParticleEventData" and _event_alias(e) == 0xEBFF97C2]
    arrive_alias, snip_alias = _hash("BLG_Recall_ArrivalFlash_Event"), _hash("BLG_Recall_SnipFlash_Event")
    arrive = [e for _, k, e in events if k == "ParticleEventData" and _event_alias(e) == arrive_alias]
    snips = [e for _, k, e in events if k == "ParticleEventData" and _event_alias(e) == snip_alias]
    if (len(dep), len(change), len(arrive), len(snips)) != (5, 2, 5, 4):
        raise ValueError(f"Unexpected recall flash counts {(len(dep), len(change), len(arrive), len(snips))}")
    expected_departures = sorted((frame, int(fmt_key(f"RC_Dash{min(i, 3)}"), 16))
                                 for i, frame in enumerate((*NEW_BLINKS, NEW_SEAT)))
    if sorted((_event_number(e, "mStartFrame"), _event_bone(e)) for e in dep) != expected_departures:
        raise ValueError("Departure flashes no longer sit on the authored departure anchors")
    expected_changes = sorted((int(round(_map_old_frame(a))), int(round(_map_old_frame(b))))
                              for a, b in ((140, 148), (190, 198)))
    if sorted((_event_number(e, "mStartFrame"), _event_number(e, "mEndFrame")) for e in change) != expected_changes:
        raise ValueError("The two trophy/doll transition flashes were not retimed")
    arrival_by_frame = sorted((_event_number(e, "mStartFrame"), _event_bone(e)) for e in arrive)
    expected_arrivals = sorted((frame, int(fmt_key("Root"), 16)) for frame in (*NEW_BLINKS, NEW_SEAT))
    if arrival_by_frame != expected_arrivals:
        raise ValueError(f"Arrival flashes do not attach to Root on new blink frames: {arrival_by_frame}")
    expected_snips = sorted((frame, int(fmt_key(f"RC_Burst{i}"), 16)) for i, frame in enumerate(NEW_CUTS))
    if sorted((_event_number(e, "mStartFrame"), _event_bone(e)) for e in snips) != expected_snips:
        raise ValueError("Snip flashes do not attach to their four flag burst bones")
    hidden = []
    body = int(fmt_key("Body"), 16)
    for _, kind, event in events:
        if kind != "SubmeshVisibilityEventData":
            continue
        hide = re.search(r"mHideSubmeshList: list\[hash\] = \{([^}]+)", event)
        if hide is None or body not in (int(v, 16) for v in re.findall(r"0x([0-9a-fA-F]+)", hide.group(1))):
            continue
        start, end = _event_number(event, "mStartFrame"), _event_number(event, "mEndFrame")
        if start is not None and end is not None:
            hidden.append((start, end))
    if sorted(hidden) != sorted((frame - 1, frame + 1) for frame in (*NEW_BLINKS, NEW_SEAT)):
        raise ValueError(f"Badge hide/show windows did not follow the blink remap: {hidden}")
    return {"departure_events": len(dep), "change_events": len(change),
            "arrival_events": len(arrive), "snip_events": len(snips),
            "hide_windows": sorted(hidden), "arrival_frames": [x[0] for x in arrival_by_frame]}


def apply(assets: dict[str, bytes], tmp: str | Path) -> dict[str, bytes]:
    """Polish recall on a seed resource map and return the same additive map."""
    work = Path(tmp)
    work.mkdir(parents=True, exist_ok=True)
    for path in (SKIN_BIN, ANIM_BIN, ANM_PATH):
        if path not in assets:
            raise KeyError(f"Seed resource is missing {path}")
    source_anm = assets[ANM_PATH]
    if _parse_anm(source_anm)[2].shape[0] != LAST + 1:
        raise ValueError("Recall ANM has an unexpected frame count")
    already_polished = _has_events(assets[ANIM_BIN], work)
    if already_polished:
        timing = {"duration_frames": LAST, "joints": _parse_anm(source_anm)[1].shape[0],
                  "blink_frames": NEW_BLINKS, "cut_frames": NEW_CUTS,
                  "seat_frame": NEW_SEAT, "swap_frame": SWAP,
                  "wave_end_frame": LAST, "already_polished": True}
    else:
        assets[ANM_PATH], timing = _retime_anm(source_anm)
    assets[SKIN_BIN] = _add_systems(assets[SKIN_BIN], work)
    assets[ANIM_BIN] = _add_events(assets[ANIM_BIN], work)
    if STAR_TEX not in assets:
        raise KeyError(f"Seed resources do not include the four-point star texture {STAR_TEX}")
    if SKL_PATH not in assets:
        raise KeyError(f"Seed resource is missing {SKL_PATH}")
    report = _check_anm(assets[ANM_PATH], assets[SKL_PATH])
    # Geometry anchors must differ: Dash is the authored old position while Root
    # has already reached the new flag target on the same blink frame.
    for i in range(5):
        if report[f"blink_{i}"]["separation"] < 30:
            raise AssertionError(f"Recall blink {i} departure and arrival overlap")
    if not report["seat"]["legs_still_animated"]:
        raise AssertionError("Recall legs stop moving before the doll transition")
    if report["wave"]["start"] != SWAP or report["wave"]["end"] != LAST:
        raise AssertionError("Recall doll wave no longer reaches the final frame")
    if report["wave"]["duration_seconds"] < 1.5:
        raise AssertionError("Recall doll wave is shorter than its approved 1.5 seconds")
    bin_report = _validate_bin_output(assets[SKIN_BIN], assets[ANIM_BIN], assets[SKL_PATH], work)
    (work / "recall-polish-report.json").write_text(
        __import__("json").dumps({"timing": timing, "attachment_points": report,
                                  "game_bin_readback": bin_report}, indent=2),
        encoding="utf-8")
    return assets
