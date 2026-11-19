"""Skin-local, game-native Gwen Q particles for the BLG finals design."""
from __future__ import annotations

from pathlib import Path
import re
from champion_layers import native_sprite, q_shards


HERE = Path(__file__).resolve().parent
ART = HERE / "art"
ASSET_ROOT = "assets/characters/gwen/skins/base/particles/blg_qw"
RIOT_ASSET_ROOT = "assets/characters/gwen/skins/base/particles/blg_qw"

ASSET_FILES = {
    f"{ASSET_ROOT}/{name}.png": ART / (name + ".png")
    for name in ("q_blade_stitch", "q_final_star", "q_cast_open", "q_cast_close",
                 "q_silk_ice", "q_silk_rose", "blg_crystal_ice", "blg_crystal_rose", "blg_crystal_gold")
}

TRAIL_EVENT_KEY = 0xadd0691d
SCISSORS_B_EVENT = 0xd4646169
DECAY_EVENT_KEY = 0x6052a5ec
TRAIL_OBJECTS = {
    "Azure": (0xadd0691d, "Gwen_BLG_Q_AzureTrail", (39, 175, 255)),
    "Rose": (None, "Gwen_BLG_Q_RoseTrail", (255, 72, 177)),
}
DECAY_OBJECT = "Gwen_BLG_Q_FinalSnip"

NATIVE_Q_CASTS = (
    (0x3d021ae0, "Gwen_Base_Q_ATK_Q1", "Gwen_BLG_Q_CastFirst", {
        "OPEN": (55, 182, 255), "CLOSE": (255, 84, 183),
        "Add_Linger": (111, 204, 255), "CLOSE_Add_Over": (255, 126, 204),
        "Temp_Mesh4": (73, 190, 255), "Temp_Mesh6": (230, 247, 255),
        "Temp_Mesh7": (255, 151, 218), "Centerppop": (255, 235, 191),
        "Flare_IMpact": (255, 246, 222), "slash": (255, 255, 255),
        "Bloom_Impact": (74, 191, 255), "Bloom_Impact1": (255, 126, 205),
        "Bloom_Impact2": (255, 237, 200), "Threads_UP01": (74, 193, 255),
        "Threads_UP_Thinner": (255, 105, 193), "Threads_DOwn01": (255, 216, 166),
        "Threads_UP_Thinner1": (255, 180, 222), "StringCircles_R": (255, 219, 158),
        "CornerStrand": (255, 221, 166), "BASE_LAYERMIST": (113, 208, 255),
        "BASE_LAYERMIST1": (145, 220, 255),
    }),
    (0x40021f99, "Gwen_Base_Q_ATK_Q2", "Gwen_BLG_Q_CastSecond", {
        "CLOSE": (255, 83, 183), "Add_Linger": (77, 183, 255),
        "CLOSE_Add_Over": (255, 143, 218), "Temp_Mesh4": (255, 130, 208),
        "Temp_Mesh6": (78, 187, 255), "Temp_Mesh7": (225, 244, 255),
        "Centerppop": (255, 237, 199), "Add_Linger1": (99, 197, 255),
        "Temp_GroundGlow1": (242, 249, 255),
        "Pattern_Alpha4": (255, 169, 221), "Pattern_Alpha5": (255, 229, 182),
    }),
    (0xbb89a3ec, "Gwen_Base_Q_ATK_Q3_Mini", "Gwen_BLG_Q_CastFinisher", {
        "OPEN": (71, 181, 255), "CLOSE": (255, 77, 178),
        "Add_Linger": (255, 242, 218), "Threads_UP_Thinner2": (255, 218, 165),
        "Threads_UP_Thinner3": (85, 195, 255), "Flare_IMpact": (255, 250, 233),
    }),
    (0x069b7564, "Gwen_Base_Q_Impact01", "Gwen_BLG_Q_ImpactFirst", {
        "Bloom_Birth": (104, 200, 255), "Bloom_Impact 2": (255, 246, 221),
        "Sparkles": (255, 176, 221), "Sparkles1": (139, 216, 255),
        "Spikes": (106, 198, 255),
    }),
    (0x099b7a1d, "Gwen_Base_Q_Impact02", "Gwen_BLG_Q_ImpactFollowup", {
        "bright_flash": (255, 248, 232), "Sparkles": (255, 170, 218),
        "Sparkles1": (107, 201, 255), "Spikes1": (89, 186, 255),
        "Activate": (255, 237, 202),
    }),
)

RIOT_TEXTURE_TRAIL = RIOT_ASSET_ROOT + "/q_blade_stitch.tex"
RIOT_TEXTURE_STAR = RIOT_ASSET_ROOT + "/q_final_star.tex"


def fnv1a(text: str) -> int:
    value = 2166136261
    for byte in text.lower().encode("utf-8"):
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return value




def _matching_brace(text: str, start: int) -> int:
    depth = 0
    quoted = False
    escaped = False
    for pos in range(start, len(text)):
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


def _entries(rito: str):
    start = rito.find("entries: map")
    if start < 0:
        raise ValueError("Missing RitoBin entries map")
    open_brace = rito.find("{", start)
    close_end = _matching_brace(rito, open_brace)
    body_start = open_brace + 1
    body_end = close_end - 1
    body = rito[body_start:body_end]
    pattern = re.compile(r"(?m)^    (0x[0-9a-fA-F]+) = ([\w]+) \{$")
    records = []
    cursor = 0
    for match in pattern.finditer(body):
        brace = body.find("{", match.start(), match.end())
        end = _matching_brace(body, brace)
        records.append((int(match[1], 16), match[2], body[match.start():end]))
        cursor = end
    return (rito[:body_start], records, rito[body_end:])


def _find_field(text: str, name: str, marker: str) -> tuple[int, int]:
    match = re.search(r"(?m)^\s*" + re.escape(name) + r": embed = " + re.escape(marker) + r" \{", text)
    if not match:
        raise ValueError(f"Missing field {name}: {marker}")
    brace = text.find("{", match.start(), match.end())
    return match.start(), _matching_brace(text, brace)


def _replace_field(text: str, name: str, marker: str, replacement: str) -> str:
    start, end = _find_field(text, name, marker)
    return text[:start] + replacement + text[end:]


def _replace_value(text: str, name: str, marker: str, interior: str) -> str:
    old_start, old_end = _find_field(text, name, marker)
    old = text[old_start:old_end]
    lead = re.match(r"\s*", old).group(0)
    return text[:old_start] + lead + f"{name}: embed = {marker} {{\n" + interior + "\n" + lead + "}" + text[old_end:]


def _top_level_resource(block: str) -> tuple[int, int]:
    match = re.search(r"(?m)^\s*resourceMap: map\[hash, link\] = \{", block)
    if not match:
        raise ValueError("Missing Gwen resourceMap")
    brace = block.find("{", match.start(), match.end())
    return match.start(), _matching_brace(block, brace)


def _tint_emitter(block: str, rgb: tuple[int, int, int], with_texture: bool) -> str:
    short = [c / 255.0 for c in rgb]
    birth = f"constantValue: vec4 = {{ {short[0]:.6f}, {short[1]:.6f}, {short[2]:.6f}, 1 }}"
    times = "times: list[f32] = { 0, 0.28, 0.76, 1 }"
    values = (
        "values: list[vec4] = {\n"
        f"    {{ {short[0]:.6f}, {short[1]:.6f}, {short[2]:.6f}, 0.9 }}\n"
        f"    {{ 1, 1, 1, 0.86 }}\n"
        f"    {{ {short[0]:.6f}, {short[1]:.6f}, {short[2]:.6f}, 0.34 }}\n"
        "    { 1, 1, 1, 0 }\n"
        "}"
    )
    color = (
        "dynamics: pointer = VfxAnimatedColorVariableData {\n"
        "    " + times + "\n    " + values.replace("\n", "\n    ") + "\n}"
    )
    if re.search(r"(?m)^\s*birthColor: embed = ValueColor \{", block):
        block = _replace_value(block, "birthColor", "ValueColor", birth)
    if re.search(r"(?m)^\s*Color: embed = ValueColor \{", block):
        block = _replace_value(block, "Color", "ValueColor", color)
    if with_texture:
        texture_match = re.search(r'(?m)^\s*texture: string = "[^"]+"', block)
        if not texture_match:
            raise ValueError("Trail emitter has no texture slot")
        indent = re.match(r"\s*", texture_match.group(0)).group(0)
        block = block[:texture_match.start()] + indent + 'texture: string = "' + RIOT_TEXTURE_TRAIL + '"' + block[texture_match.end():]
    return block


def _authored_tint_emitter(block: str, rgb: tuple[int, int, int]) -> str:
    """Recolor existing curves while keeping their alpha, timing and shading."""
    color = tuple(channel / max(rgb) for channel in rgb)

    def remap_vectors(value_block: str) -> str:
        pattern = re.compile(
            r"\{\s*([+-]?(?:\d*\.)?\d+(?:[eE][+-]?\d+)?),\s*"
            r"([+-]?(?:\d*\.)?\d+(?:[eE][+-]?\d+)?),\s*"
            r"([+-]?(?:\d*\.)?\d+(?:[eE][+-]?\d+)?),\s*"
            r"([+-]?(?:\d*\.)?\d+(?:[eE][+-]?\d+)?)\s*\}"
        )

        def replace(match):
            source = [float(match.group(i)) for i in range(1, 5)]
            peak = max(source[:3])
            mapped = [peak * channel for channel in color]
            return "{ " + ", ".join(f"{channel:.7g}" for channel in mapped) + f", {source[3]:.7g} }}"

        return pattern.sub(replace, value_block)

    for field in ("birthColor", "Color"):
        try:
            start, end = _find_field(block, field, "ValueColor")
        except ValueError:
            continue
        previous = block[start:end]
        block = block[:start] + remap_vectors(previous) + block[end:]
    return block


def _edit_native_cast(source: str, new_name: str, path: str, object_hash: int,
                      emitter_tints: dict[str, tuple[int, int, int]]) -> str:
    matches = list(re.finditer(r"(?m)^\s*VfxEmitterDefinitionData \{", source))
    for match in reversed(matches):
        start = match.start()
        end = _matching_brace(source, source.find("{", start, match.end()))
        emitter = source[start:end]
        emitter_name = re.search(r'(?m)^\s*emitterName: string = "([^"]+)"', emitter)
        if emitter_name and emitter_name[1] in emitter_tints:
            tint = (255,255,255) if emitter_name[1] in {"OPEN", "CLOSE"} else emitter_tints[emitter_name[1]]
            emitter = _authored_tint_emitter(emitter, tint)
            for number, stroke in (("01", "open"), ("02", "close")):
                emitter = emitter.replace(f"ASSETS/Characters/Gwen/Skins/Base/Particles/Q_MeshTrail{number}.tex",
                                          f"{ASSET_ROOT}/q_cast_{stroke}.tex")
        source = source[:start] + emitter + source[end:]
    for stage in ("First", "Second", "Finisher"):
        if new_name.endswith("Cast"+stage):
            token = "complexEmitterDefinitionData: list[pointer] = {"
            assert source.count(token)==1
            source = source.replace(token,token+"\n"+"\n".join(native_sprite(s) for s in q_shards(stage)))
    return _edit_system(source, new_name, path, object_hash)


def _edit_system(source: str, new_name: str, path: str, object_hash: int,
                 tint: tuple[int, int, int] | None = None, add_star: bool = False) -> str:
    emitter_matches = list(re.finditer(r"(?m)^\s*VfxEmitterDefinitionData \{", source))
    for match in reversed(emitter_matches):
        open_brace = source.find("{", match.start(), match.end())
        end = _matching_brace(source, open_brace)
        emitter = source[match.start():end]
        name_match = re.search(r'(?m)^\s*emitterName: string = "([^"]+)"', emitter)
        if tint and name_match and name_match[1] in {"DarkBG_Ribbon", "MistTrail1_Add01", "Sharp_Edge_Bright"}:
            emitter = _tint_emitter(emitter, tint, name_match[1] in {"DarkBG_Ribbon", "MistTrail1_Add01"})
            if name_match[1] in {"DarkBG_Ribbon", "MistTrail1_Add01"}:
                emitter = _replace_value(emitter, "particleLifetime", "ValueFloat",
                                         "                    constantValue: f32 = 0.23")
                emitter = re.sub(r"texDiv: vec2 = \{ [^}]+ \}", "texDiv: vec2 = { 1, 1 }", emitter)
        if add_star and name_match and name_match[1] == "Longer_Bloom":
            star = emitter
            star = re.sub(r'(?m)^\s*timeBeforeFirstEmission: f32 = [^\n]+', "                timeBeforeFirstEmission: f32 = 0.12", star)
            star = re.sub(r'(?m)^\s*particleLifetime: embed = ValueFloat \{\n\s*constantValue: f32 = [^\n]+\n\s*\}', "                particleLifetime: embed = ValueFloat {\n                    constantValue: f32 = 0.24\n                }", star, count=1)
            star = re.sub(r'(?m)^\s*lifetime: option\[f32\] = \{ [^}]+\}', "                lifetime: option[f32] = { 0.38 }", star, count=1)
            star = re.sub(r'(?m)^\s*emitterName: string = "[^"]+"', '                emitterName: string = "BLG_FinalSnip_Star"', star, count=1)
            star = re.sub(r'(?m)^\s*EmitterPosition: embed = ValueVector3 \{\n\s*constantValue: vec3 = \{[^}]+\}\n\s*\}', "                EmitterPosition: embed = ValueVector3 {\n                    constantValue: vec3 = { 0, 0, -80 }\n                }", star, count=1)
            star = re.sub(r'(?m)^\s*birthScale0: embed = ValueVector3 \{\n\s*constantValue: vec3 = \{[^}]+\}\n\s*\}', "                birthScale0: embed = ValueVector3 {\n                    constantValue: vec3 = { 181, 181, 0 }\n                }", star, count=1)
            star = _tint_emitter(star, (255, 255, 255), False)
            texture_match = re.search(r'(?m)^\s*texture: string = "[^"]+"', star)
            indent = re.match(r"\s*", texture_match.group(0)).group(0)
            star = star[:texture_match.start()] + indent + 'texture: string = "' + RIOT_TEXTURE_STAR + '"' + star[texture_match.end():]
            star += "\n"
            source = source[:end] + star + source[end:]
        source = source[:match.start()] + emitter + source[end:]
    for field, value in (
        ("particleName", f'"{new_name}"'),
        ("particlePath", f'"{path}"'),
        ("objectPath", f"0x{object_hash:08x}"),
    ):
        pattern = re.compile(r"(?m)^(\s*" + re.escape(field) + r": (?:string|hash) = )[^\n]+")
        source, count = pattern.subn(lambda m: m[1] + value, source, count=1)
        if not count:
            raise ValueError(f"Missing VfxSystem field {field}")
    source, count = re.subn(
        r"(?m)^    0x[0-9a-fA-F]+ = VfxSystemDefinitionData \{$",
        f"    0x{object_hash:08x} = VfxSystemDefinitionData {{",
        source, count=1)
    if count != 1:
        raise ValueError("Could not assign the skin-local VFX bin object hash")
    return source


def _skin_edits(skin_text: str):
    prefix, entries, suffix = _entries(skin_text)
    by_type_name = {}
    resolver_key = None
    for index, kind, block in entries:
        particle = re.search(r'(?m)^\s*particleName: string = "([^"]+)"', block)
        if kind == "VfxSystemDefinitionData" and particle:
            by_type_name[particle[1]] = (index, block)
        if kind == "ResourceResolver":
            resolver_key = index
    required = [
        "Gwen_Base_Q_WeaponTrail_ATK01",
        "Gwen_Base_Q_WeaponTrail_ATK01_Decay",
    ]
    required.extend(source_name for _, source_name, _, _ in NATIVE_Q_CASTS)
    if resolver_key is None or any(name not in by_type_name for name in required):
        raise ValueError("The Gwen Skin0 BIN is missing the native Q particle systems")
    resolver = next(block for index, kind, block in entries if index == resolver_key)
    rstart, rend = _top_level_resource(resolver)
    resource_field = resolver[rstart:rend]
    mappings = {int(key, 16): int(value, 16) for key, value in
                re.findall(r"(0x[0-9a-fA-F]+) = (0x[0-9a-fA-F]+)", resource_field)}
    cast_aliases = {alias: source for alias, source, _, _ in NATIVE_Q_CASTS}
    for key in (TRAIL_EVENT_KEY, DECAY_EVENT_KEY, *cast_aliases):
        if key not in mappings:
            raise ValueError(f"Q resolver alias 0x{key:08x} is missing from Gwen Skin0")

    trail_key = TRAIL_EVENT_KEY
    base_trail_path = "Characters/Gwen/Skins/Skin0/Particles/"
    added_entries = []
    trail_objects = {}
    rose_alias = fnv1a("Gwen_BLG_Q_RoseTrail_Event")
    if rose_alias in mappings or rose_alias in (TRAIL_EVENT_KEY, DECAY_EVENT_KEY):
        raise ValueError("The unique Q rose event alias already exists")
    for label, (alias, name, color) in TRAIL_OBJECTS.items():
        if alias is None:
            alias = rose_alias
        path = base_trail_path + name
        object_hash = fnv1a(path)
        source = by_type_name["Gwen_Base_Q_WeaponTrail_ATK01"][1]
        updated = _edit_system(source, name, path, object_hash, tint=color)
        added_entries.append((object_hash, "VfxSystemDefinitionData", updated))
        trail_objects[label] = (alias, object_hash, path)

    fin_name = DECAY_OBJECT
    fin_path = base_trail_path + fin_name
    fin_hash = fnv1a(fin_path)
    final_star = _edit_system(by_type_name["Gwen_Base_Q_WeaponTrail_ATK01_Decay"][1],
                              fin_name, fin_path, fin_hash, tint=(227, 242, 255), add_star=True)
    added_entries.append((fin_hash, "VfxSystemDefinitionData", final_star))

    authored_objects = {}
    for alias, source_name, target_name, emitter_tints in NATIVE_Q_CASTS:
        path = base_trail_path + target_name
        object_hash = fnv1a(path)
        source = by_type_name[source_name][1]
        updated = _edit_native_cast(source, target_name, path, object_hash, emitter_tints)
        added_entries.append((object_hash, "VfxSystemDefinitionData", updated))
        authored_objects[alias] = object_hash
    if len({key for key, _, _ in added_entries}) != len(added_entries):
        raise ValueError("Skin-local Q effect hash collision")
    for key, _, _ in added_entries:
        if any(index == key for index, _, _ in entries):
            raise ValueError(f"Skin-local Q effect object 0x{key:08x} already exists")

    mappings_to_targets = {
        TRAIL_EVENT_KEY: trail_objects["Azure"][1],
        DECAY_EVENT_KEY: fin_hash,
        **authored_objects,
    }
    for alias, object_hash in mappings_to_targets.items():
        resource_field, count = re.subn(
            r"(?m)^(\s*0x0*" + f"{alias:x}" + r" = )0x[0-9a-fA-F]+",
            lambda m, target=object_hash: m[1] + f"0x{target:08x}",
            resource_field, count=1)
        if count != 1:
            raise ValueError(f"Could not redirect Q resolver alias 0x{alias:08x}")
    line_indent = "            "
    resource_field = resource_field[:-1] + f"\n{line_indent}0x{rose_alias:08x} = 0x{trail_objects['Rose'][1]:08x}\n        }}"
    resolver = resolver[:rstart] + resource_field + resolver[rend:]
    entries = [(key, kind, resolver if key == resolver_key else block)
               for key, kind, block in entries]
    entries.extend(added_entries)
    result = prefix + "\n" + "\n".join(block for _, _, block in entries) + "\n" + suffix
    return result, rose_alias


def _animation_edit(anim_text: str, rose_alias: int) -> str:
    result = anim_text
    # Redirect only the Scissors_B instance of the shared Q trail event.
    pattern = re.compile(r"(?m)^\s*0xd4646169 = ParticleEventData \{$")
    matched = 0
    for match in reversed(list(pattern.finditer(result))):
        open_brace = result.find("{", match.start(), match.end())
        end = _matching_brace(result, open_brace)
        event = result[match.start():end]
        if ("mEffectKey: hash = 0xadd0691d" not in event or
                "mBoneName: hash = 0xbaf87f4b" not in event):
            continue
        event, n = re.subn(r"(?m)^(\s*mEffectKey: hash = )0xadd0691d$",
                           lambda m: m[1] + f"0x{rose_alias:x}", event, count=1)
        if n != 1:
            raise ValueError("Could not redirect Q's Scissors_B event")
        result = result[:match.start()] + event + result[end:]
        matched += 1
    if matched < 2:
        raise ValueError(f"Expected Q initial and follow-up B blade events, found {matched}")
    graph_path = HERE.parent / "rig-study" / "graph_inventory.json"
    graph = __import__("json").loads(graph_path.read_text(encoding="utf-8"))
    finisher_sources = {
        "spell1_c-179.anm", "spell1_c-90.anm", "spell1_c90.anm", "spell1_c179.anm"
    }
    target_ids = {
        int(row["graphClipKey"], 16)
        for row in graph["clips"]
        if Path(row["sourcePath"]).name in finisher_sources
    }
    if len(target_ids) != 4:
        raise ValueError(f"Expected four authored directional Q finisher clips, got {len(target_ids)}")
    replacements = []
    for key in target_ids:
        pattern = re.compile(r"(?m)^\s*0x0*" + f"{key:x}" + r" = AtomicClipData \{$")
        matches = list(pattern.finditer(result))
        if len(matches) != 1:
            raise ValueError(f"Directional Q finisher clip 0x{key:08x} is missing")
        clip_match = matches[0]
        clip_open = result.find("{", clip_match.start(), clip_match.end())
        clip_end = _matching_brace(result, clip_open)
        clip = result[clip_match.start():clip_end]
        marker = re.search(r"(?m)^\s*mEventDataMap: map\[hash, pointer\] = \{", clip)
        if not marker:
            raise ValueError(f"Directional Q clip 0x{key:08x} has no event map")
        map_open = clip.find("{", marker.start(), marker.end())
        map_end = _matching_brace(clip, map_open)
        event_key = re.search(r"(?m)^\s*0xd4646169 = ParticleEventData \{", clip[map_open:map_end])
        if event_key:
            raise ValueError(f"Directional Q clip 0x{key:08x} already has a Scissors_B trail event")
        event = (
            "                    0xd4646169 = ParticleEventData {\n"
            "                        mEffectKey: hash = 0x6052a5ec\n"
            "                        mParticleEventDataPairList: list[embed] = {\n"
            "                            ParticleEventDataPair {\n"
            "                                mBoneName: hash = 0xbaf87f4b\n"
            "                            }\n"
            "                        }\n"
            "                        mScalePlaySpeedWithAnimation: bool = true\n"
            "                    }"
        )
        clip = clip[:map_end - 1] + "\n" + event + "\n" + clip[map_end - 1:]
        replacements.append((clip_match.start(), clip_end, clip))
    for start, end, clip in sorted(replacements, reverse=True):
        result = result[:start] + clip + result[end:]
    return result


def apply(skin_text: str, anim_text: str) -> tuple[str, str]:
    """Return updated Gwen Skin0 and animation graph Rito source."""
    new_skin, rose_alias = _skin_edits(skin_text)
    new_anim = _animation_edit(anim_text, rose_alias)
    return new_skin, new_anim
