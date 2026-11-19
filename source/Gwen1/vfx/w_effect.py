"""Skin-local, game-native Gwen W particle texture overrides.

The cast, move and decay use the stock W graph, geometry and coordinates.
The wall carries two moving silk currents above an embroidered floor,
with a camera-facing BLG mark and a continuous field of rising crystals.
"""
from __future__ import annotations

import re
from pathlib import Path
from champion_layers import CUP_ALPHA, CUP_HALF_SIZE, CUP_YAW, CURRENT_SPEEDS, SEAL, native_sprite, w_motes


HERE = Path(__file__).resolve().parent
ART = HERE / "art"
ASSET_ROOT = "assets/characters/gwen/skins/base/particles/blg_qw/"

TEXTURES = {
    "w_mistfield": ART / "w_mistfield.png",
    "w_outer_braid": ART / "w_outer_braid.png",
    "w_corner_gem": ART / "w_corner_gem.png",
    "w_corner_glint": ART / "w_corner_glint.png",
    "w_thread_trail": ART / "w_thread_trail.png",
    "w_sewing_glint": ART / "w_sewing_glint.png",
    **{name: ART / (name + ".png") for name in (
        "w_blg_wordmark", "w_current_ice", "w_current_rose", "w_stitch_orbit", "w_worlds_cup",
        "blg_crystal_ice", "blg_crystal_rose", "blg_crystal_gold")},
}

# Every binding below is a Gwen Skin0 W object already used by the stock
# ResourceResolver. They are edited in place, so all aliases continue to
# resolve to the same native effect graph and the stock skill event timeline.
EMITTER_TEXTURES = {
    "Gwen_Base_W_MistArea": {
        "Blend_FLoor": "w_mistfield",
        "Wall_Strings": "w_outer_braid",
        "Wall_Strings1": "w_outer_braid",
        "CornerRune_BLOOM1": "w_corner_gem",
        "CornerRune_BLOOM2": "w_corner_glint",
    },
    "Gwen_Base_W_Mist_MovingCast": {
        "Bloom_WALL": "w_outer_braid",
        "CornerRune": "w_corner_gem",
        "CornerRune_BLOOM": "w_corner_glint",
    },
    "Gwen_Base_W_MistArea_DecayVis": {
        "Bloom_WALL": "w_outer_braid",
        "CornerRune_BLOOM1": "w_corner_gem",
        "CornerRune_BLOOM": "w_corner_glint",
    },
    "Gwen_Base_W_WeaponTrail_Generic": {
        "Strands_Ribbon": "w_thread_trail",
    },
}

_TOP_ENTRY = re.compile(r"(?m)^    (0x[0-9a-fA-F]+) = (\w+) \{")
_EMITTER = re.compile(r"(?m)^\s+VfxEmitterDefinitionData \{")
_FIELD = re.compile(r"(?m)^\s*([\w~]+):")
_VECTOR4 = re.compile(
    r"(vec4\s*=\s*\{\s*)"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
    r"(\s*,\s*)"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
    r"(\s*,\s*)"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
    r"(\s*,\s*)"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
    r"(\s*\})"
)


def texture_references() -> dict[str, Path]:
    """Return the native lower-case TEX path to its authored PNG source."""
    return {ASSET_ROOT + f"{stem}.tex": path for stem, path in TEXTURES.items()}


def _matching_brace(text: str, open_at: int) -> int:
    depth = 0
    quoted = False
    escaped = False
    for pos in range(open_at, len(text)):
        char = text[pos]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return pos + 1
    raise ValueError("Unclosed RitoBin block")


def _field_bounds(block: str, name: str) -> tuple[int, int] | None:
    match = re.search(
        r"(?m)^\s*" + re.escape(name) + r":\s*embed\s*=\s*\w+\s*\{", block
    )
    if not match:
        return None
    open_at = block.find("{", match.start(), match.end())
    return match.start(), _matching_brace(block, open_at)


def _neutralize_rgb(block: str) -> str:
    """Make authored RGB authoritative while retaining every alpha keyframe."""
    edits: list[tuple[int, int, str]] = []
    for field in ("birthColor", "Color"):
        bounds = _field_bounds(block, field)
        if not bounds:
            continue
        start, end = bounds
        old = block[start:end]

        def white_rgb(match: re.Match[str]) -> str:
            return (match[1] + "1" + match[3] + "1" + match[5] + "1"
                    + match[7] + match[8] + match[9])

        new = _VECTOR4.sub(white_rgb, old)
        # List entries omit the vec4 prefix in RitoBin's text format.
        keys = re.search(r"values: list\[vec4\] = \{", new)
        if keys:
            end_keys = _matching_brace(new, keys.end() - 1)
            values = re.sub(r"\{\s*[-+.\deE]+\s*,\s*[-+.\deE]+\s*,\s*[-+.\deE]+\s*,\s*([-+.\deE]+)\s*\}",
                            r"{ 1, 1, 1, \1 }", new[keys.end():end_keys])
            new = new[:keys.end()] + values + new[end_keys:]
        if new != old:
            edits.append((start, end, new))
    for start, end, new in reversed(edits):
        block = block[:start] + new + block[end:]
    return block


def _edit_emitter(block: str, stem: str) -> str:
    texture_path = ASSET_ROOT + stem + ".tex"
    match = re.search(r'(?m)^(\s*texture:\s*string\s*=\s*)"[^"]*"', block)
    if not match:
        raise ValueError("Target W emitter is missing its direct texture field")
    block = block[:match.start()] + match[1] + '"' + texture_path + '"' + block[match.end():]
    return _neutralize_rgb(block)


def _replace_field(block: str, name: str, value: str) -> str:
    indent = re.search(r"(?m)^([ ]+)emitterName:", block)[1]
    match = re.search(r"(?m)^" + indent + re.escape(name) + r": [^\n]+", block)
    if match is None:
        raise ValueError(f"Missing wall particle field {name}")
    brace = block.find("{", match.start(), match.end())
    end = match.end() if brace == -1 else _matching_brace(block, brace)
    return block[:match.start()] + indent + name + ": " + value + block[end:]


def _wall_uv(block: str) -> str:
    for name, kind, value in (
        ("birthRotation0", "3", "0, 0, 0"), ("birthUVOffset", "2", "0, 0"),
        ("birthUvScrollRate", "2", "0, 0"), ("uvScale", "2", "1, 1"),
    ):
        block = _replace_field(block, name, f"embed = ValueVector{kind} {{ constantValue: vec{kind} = {{ {value} }} }}")
    return block


def _sewing_glint(wall: str) -> str:
    settings = {
        "emitterName": 'string = "BLG_W_SewingGlint"',
        "timeBeforeFirstEmission": "f32 = 0.04",
        "lifetime": "option[f32] = { 0.7 }",
        "particleLifetime": "embed = ValueFloat { constantValue: f32 = 0.65 }",
        "particleLinger": "option[f32] = { 0 }",
        "birthUvScrollRate": "embed = ValueVector2 { constantValue: vec2 = { -1.53846, 0 } }",
        "Color": """embed = ValueColor {
                    dynamics: pointer = VfxAnimatedColorVariableData {
                        times: list[f32] = { 0, 0.08, 0.88, 1 }
                        values: list[vec4] = {
                            { 1, 1, 1, 0 }
                            { 1, 1, 1, 1 }
                            { 1, 1, 1, 1 }
                            { 1, 1, 1, 0 }
                        }
                    }
                }""",
        "texture": f'string = "{ASSET_ROOT}w_sewing_glint.tex"',
    }
    for name, value in settings.items():
        wall = _replace_field(wall, name, value)
    return wall


def _edit_system(block: str, particle_name: str) -> tuple[str, set[str]]:
    requested = EMITTER_TEXTURES[particle_name]
    starts = list(_EMITTER.finditer(block))
    edits: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for match in starts:
        start = match.start()
        open_at = block.find("{", start, match.end())
        end = _matching_brace(block, open_at)
        emitter = block[start:end]
        name_match = re.search(r'(?m)^\s*emitterName:\s*string\s*=\s*"([^"]+)"', emitter)
        if not name_match or name_match[1] not in requested:
            continue
        name = name_match[1]
        if name in seen:
            raise ValueError(f"Duplicate target W emitter {particle_name}/{name}")
        seen.add(name)
        styled = _edit_emitter(emitter, requested[name])
        if requested[name] == "w_outer_braid":
            styled = _wall_uv(styled)
            if particle_name == "Gwen_Base_W_MistArea" and name == "Wall_Strings":
                wall = styled
                styled += "\n" + _sewing_glint(wall).lstrip("\n")
                for shade, speed in CURRENT_SPEEDS.items():
                    flowing = wall
                    for field, value in {
                        "emitterName": f'string = "BLG_W_SilkCurrent_{shade}"',
                        "texture": f'string = "{ASSET_ROOT}w_current_{shade}.tex"',
                        "birthUvScrollRate": f"embed = ValueVector2 {{ constantValue: vec2 = {{ {speed}, 0 }} }}",
                        "timeBeforeFirstEmission": "f32 = 0.08",
                        "particleLifetime": "embed = ValueFloat { constantValue: f32 = 9 }",
                        "lifetime": "option[f32] = { 9 }",
                        "Color": "embed = ValueColor { constantValue: vec4 = { 1, 1, 1, 0.91 } }",
                        "birthScale0": ("embed = ValueVector3 { constantValue: vec3 = { 1.52, 3.2, 1.52 } }"
                                        if shade=="ice" else "embed = ValueVector3 { constantValue: vec3 = { 1.65, 2.7, 1.65 } }"),
                    }.items():
                        flowing = _replace_field(flowing, field, value)
                    styled += "\n"+flowing.lstrip("\n")
        if particle_name == "Gwen_Base_W_MistArea" and name == "Blend_FLoor":
            lace = styled
            for field, value in {
                "emitterName": 'string = "BLG_W_StitchOrbit"',
                "texture": f'string = "{ASSET_ROOT}w_stitch_orbit.tex"',
                "textureMult": 'pointer = VfxTextureMultDefinitionData { textureMult: string = "ASSETS/Characters/Gwen/Skins/Base/Particles/Draven_Base_W_Color-hold.tex" }',
                "pass": "i16 = -2850",
                "birthScale0": "embed = ValueVector3 { constantValue: vec3 = { 402, 402, 0 } }",
                "scale0": "embed = ValueVector3 { constantValue: vec3 = { 1, 1, 1 } }",
                "birthRotationalVelocity0": "embed = ValueVector3 { constantValue: vec3 = { 0, 9, 0 } }",
            }.items():
                lace = _replace_field(lace,field,value)
            styled += "\n"+lace.lstrip("\n")
            cup = lace
            width,height=CUP_HALF_SIZE
            for field,value in {
                "emitterName": 'string = "BLG_W_SummonersCup"',
                "texture": f'string = "{ASSET_ROOT}w_worlds_cup.tex"',
                "pass": "i16 = -2800",
                "isUniformScale": "flag = false",
                "birthScale0": f"embed = ValueVector3 {{ constantValue: vec3 = {{ {width}, {height}, 0 }} }}",
                "birthRotationalVelocity0": "embed = ValueVector3 { constantValue: vec3 = { 0, 0, 0 } }",
                "birthRotation0": f"embed = ValueVector3 {{ constantValue: vec3 = {{ -90, {CUP_YAW}, 0 }} }}",
                "uvRotation": "embed = ValueFloat { constantValue: f32 = 0 }",
                "birthColor": f"embed = ValueColor {{ constantValue: vec4 = {{ 1, 1, 1, {CUP_ALPHA} }} }}",
            }.items():
                cup=_replace_field(cup,field,value)
            # Finish appearing with the cast, then follow the parent mist area.
            cup=cup.replace("times: list[f32] = { 0, 0.1, 0.5, 0.8, 1 }",
                            "times: list[f32] = { 0, 0.032, 0.5, 0.96, 1 }")
            styled += "\n"+cup.lstrip("\n")
            styled += "\n"+"\n".join(native_sprite(item) for item in (SEAL,*w_motes()))
        edits.append((start, end, styled))
    if seen != set(requested):
        raise ValueError(f"W emitter map changed for {particle_name}: missing {sorted(set(requested)-seen)}")
    for start, end, new in reversed(edits):
        block = block[:start] + new + block[end:]
    return block, seen


def apply(skin_text: str, anim_text: str) -> tuple[str, str]:
    """Restyle Gwen W emitters in-place; preserve every native graph link."""
    headers = list(_TOP_ENTRY.finditer(skin_text))
    rewrites: list[tuple[int, int, str]] = []
    found: set[str] = set()
    for index, header in enumerate(headers):
        if header[2] != "VfxSystemDefinitionData":
            continue
        start = header.start()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(skin_text)
        block = skin_text[start:end]
        name_match = re.search(r'(?m)^\s*particleName:\s*string\s*=\s*"([^"]+)"', block)
        if not name_match or name_match[1] not in EMITTER_TEXTURES:
            continue
        particle_name = name_match[1]
        if particle_name in found:
            raise ValueError(f"Duplicate Gwen W particle system {particle_name}")
        found.add(particle_name)
        edited, _ = _edit_system(block, particle_name)
        rewrites.append((start, end, edited))
    if found != set(EMITTER_TEXTURES):
        raise ValueError(f"Missing Gwen W systems: {sorted(set(EMITTER_TEXTURES)-found)}")
    for start, end, edited in reversed(rewrites):
        skin_text = skin_text[:start] + edited + skin_text[end:]
    # All W animation event and cast/move/hold/decay timing stays native.
    return skin_text, anim_text
