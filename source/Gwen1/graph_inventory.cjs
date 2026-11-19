// Run the read-only Gwen WAD extractor with graph-referenced clip paths added.
// All extracted output stays in this task's rig-study directory.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const scriptPath = path.join(__dirname, 'read_base_rig.cjs');
let source = fs.readFileSync(scriptPath, 'utf8');
const graphWrite = "if (name.includes('/animations/')) fs.writeFileSync(path.join(out,'animation-skin0.bin'),b);";
const skinWrite = graphWrite + "\n    if (name.includes('/skins/skin0.bin')) fs.writeFileSync(path.join(out,'skin0.bin'),b);";
if (!source.includes(graphWrite)) throw new Error('Could not find config extraction point');
source = source.replace(graphWrite, skinWrite);
const insertion = `
const ritoText = fs.readFileSync(path.join(out, 'animation-skin0.rito'), 'utf8');
const graphFileHashes = new Set([...ritoText.matchAll(/file = 0x([0-9a-f]{1,16})/g)].map(m => m[1].padStart(16, '0')));
const hashFile = path.resolve(__dirname, '../../tool/hashes.game.txt');
for (const line of fs.readFileSync(hashFile, 'utf8').split('\\n')) {
    const m = line.match(/^([0-9a-f]{16})\\s+(.+?)\\r?$/);
    if (m && graphFileHashes.has(m[1]) && m[2].startsWith('assets/characters/gwen/skins/base/animations/') && m[2].endsWith('.anm')) names.push(m[2]);
}
const uniqueNames = [...new Set(names)];
names.splice(0, names.length, ...uniqueNames);
console.log('Graph-referenced Gwen clips:', names.length);
`;
const marker = 'for(const name of names) {';
if (!source.includes(marker)) throw new Error('Could not find extraction insertion point');
const patched = source.replace(marker, insertion + '\n' + marker);
const wadPath = process.argv[2];
if (!wadPath) throw new Error('Pass the Gwen.wad.client path');
const sandboxProcess = { argv: [process.execPath, scriptPath, wadPath] };
vm.runInNewContext(patched, { require, process: sandboxProcess, __dirname: path.dirname(scriptPath), Buffer, console }, { filename: scriptPath });

// Index every AtomicClipData node, preserving multiple graph keys that point
// at one animation file. The readable rito file was decoded with the local
// bintypes/binfields tables stored alongside this inventory.
const studyDir = path.join(__dirname, 'rig-study');
const readableRito = fs.readFileSync(path.join(studyDir, 'animation-skin0_named.rito'), 'utf8');
const hashLines = fs.readFileSync(path.resolve(__dirname, '../../tool/hashes.game.txt'), 'utf8').split('\n');
const assetPathsByHash = new Map();
for (const line of hashLines) {
    const match = line.match(/^([0-9a-f]{16})\s+(.+?)\r?$/);
    if (match) assetPathsByHash.set(match[1], match[2]);
}
const boneNamesByHash = new Map();
const skl = fs.readFileSync(path.join(studyDir, 'gwen_base.skl'));
const jointCount = skl.readUInt16LE(14);
const jointTableOffset = skl.readUInt32LE(20);
function fnv1a32(value) {
    let hash = 0x811c9dc5;
    for (const byte of Buffer.from(value.toLowerCase(), 'utf8')) hash = Math.imul(hash ^ byte, 0x01000193) >>> 0;
    return hash.toString(16).padStart(8, '0');
}
for (let index = 0; index < jointCount; index++) {
    const offset = jointTableOffset + index * 100;
    const boneHash = skl.readUInt32LE(offset + 8).toString(16).padStart(8, '0');
    const nameOffset = offset + 96 + skl.readInt32LE(offset + 96);
    const end = skl.indexOf(0, nameOffset);
    const boneName = skl.subarray(nameOffset, end).toString('utf8');
    boneNamesByHash.set(boneHash, boneName);
    boneNamesByHash.set(fnv1a32(boneName), boneName);
}
const submeshNamesByHash = new Map([
    ['88b14dc2', 'Needle'], ['19ed5bcc', 'Doll'], ['dbaa7975', 'Body'],
    ['09f0bcf6', 'Scissors'], ['72e32265', 'Scissors_A_Smear'],
]);
const skinRitoPath = path.join(studyDir, 'skin0_named.rito');
const skinRito = fs.readFileSync(skinRitoPath, 'utf8');
const skinLines = skinRito.split('\n');
const resourceResolver = new Map();
const stringValuesByFNV = new Map();
let inResolverMap = false;
for (const line of skinLines) {
    const indent = line.length - line.trimStart().length;
    const trimmed = line.trim();
    if (trimmed.startsWith('resourceMap: map[hash, link] = {')) { inResolverMap = true; continue; }
    if (inResolverMap && indent === 8 && trimmed === '}') { inResolverMap = false; continue; }
    if (inResolverMap) {
        const pair = trimmed.match(/^(0x[0-9a-f]+) = (0x[0-9a-f]+)$/);
        if (pair) resourceResolver.set(pair[1].slice(2).padStart(8, '0'), pair[2].slice(2).padStart(8, '0'));
    }
    const stringIndex = line.indexOf('string = ');
    if (stringIndex >= 0) {
        const quoteStart = line.indexOf('"', stringIndex);
        const quoteEnd = line.lastIndexOf('"');
        if (quoteStart >= 0 && quoteEnd > quoteStart) {
            const value = line.slice(quoteStart + 1, quoteEnd);
            const hash = fnv1a32(value);
            if (!stringValuesByFNV.has(hash)) stringValuesByFNV.set(hash, []);
            stringValuesByFNV.get(hash).push(value);
        }
    }
}
const initialHideLine = skinLines.find(line => line.trimStart().startsWith('initialSubmeshToHide: string = '));
const renderOrderLine = skinLines.find(line => line.trimStart().startsWith('submeshRenderOrder: string = '));
const skn = fs.readFileSync(path.join(studyDir, 'gwen_base.skn'));
const sknPartCount = skn.readUInt32LE(8);
const sknSectionNames = [];
for (let index = 0; index < sknPartCount; index++) {
    const offset = 12 + index * 80;
    const end = skn.indexOf(0, offset);
    sknSectionNames.push(skn.subarray(offset, end).toString('utf8'));
}
function quotedValue(line) {
    if (!line) return null;
    const first = line.indexOf('"'), last = line.lastIndexOf('"');
    return first >= 0 && last > first ? line.slice(first + 1, last) : null;
}
const skinDefaults = {
    initialSubmeshToHide: quotedValue(initialHideLine),
    initiallyHiddenSubmeshes: (quotedValue(initialHideLine) || '').split(/\s+/).filter(Boolean),
    submeshRenderOrder: quotedValue(renderOrderLine),
    submeshSectionNames: sknSectionNames,
    initiallyVisibleByDefaultSubmeshes: sknSectionNames.filter(name => !(quotedValue(initialHideLine) || '').split(/\s+/).includes(name)),
    resolverEvidence: 'skin0_named.rito ResourceResolver.resourceMap plus FNV-1a path hash crosswalk of declared particlePath strings',
};
function resolveEffect(effectKey) {
    if (!effectKey || !effectKey.startsWith('0x')) return null;
    const key = effectKey.slice(2).padStart(8, '0');
    const pathHash = resourceResolver.get(key);
    if (!pathHash) return { resolverKey: effectKey, resolvedHash: null, particlePath: null };
    const candidates = stringValuesByFNV.get(pathHash) || [];
    const particlePath = candidates.find(value => value.startsWith('Characters/Gwen/Skins/Skin0/Particles/')) || null;
    return { resolverKey: effectKey, resolvedHash: '0x' + pathHash, particlePath };
}
const sourceLines = readableRito.split('\n');
const clipMapLine = sourceLines.findIndex(line => line.trimStart().startsWith('mClipDataMap:'));
const trackMapLine = sourceLines.findIndex(line => line.trimStart().startsWith('mTrackDataMap:'));
const blendMapLine = sourceLines.findIndex(line => line.trimStart().startsWith('mBlendDataTable:'));
if (clipMapLine < 0 || trackMapLine < 0 || blendMapLine < 0) throw new Error('AnimationGraphData tables were not found');
const graphNodesRaw = [];
let activeNode = null;
for (const line of sourceLines.slice(clipMapLine + 1, trackMapLine)) {
    const indent = line.length - line.trimStart().length;
    if (indent === 12 && line.includes(' = ') && line.trim().endsWith('{')) {
        if (activeNode) graphNodesRaw.push(activeNode);
        const [key, type] = line.trim().split(' = ');
        activeNode = { key, type: type.split(' ')[0], lines: [] };
    }
    if (activeNode) activeNode.lines.push(line);
}
if (activeNode) graphNodesRaw.push(activeNode);
const rawClips = graphNodesRaw.filter(node => node.type === 'AtomicClipData');
const rawTracks = [];
activeNode = null;
for (const line of sourceLines.slice(trackMapLine + 1, blendMapLine)) {
    const indent = line.length - line.trimStart().length;
    if (indent === 12 && line.includes(' = TrackData {')) {
        if (activeNode) rawTracks.push(activeNode);
        const [key, type] = line.trim().split(' = ');
        activeNode = { key, type: type.split(' ')[0], lines: [] };
    }
    if (activeNode) activeNode.lines.push(line);
}
if (activeNode) rawTracks.push(activeNode);
const blendEntries = [];
let activeBlend = null;
for (const line of sourceLines.slice(blendMapLine + 1)) {
    const indent = line.length - line.trimStart().length;
    const trimmed = line.trim();
    if (indent === 12 && (trimmed.includes(' = TimeBlendData {') || trimmed.includes(' = TransitionClipBlendData {'))) {
        if (activeBlend) blendEntries.push(activeBlend);
        const [key, type] = trimmed.split(' = ');
        activeBlend = { blendTableKey: key, type: type.split(' ')[0], lines: [] };
    }
    if (activeBlend) activeBlend.lines.push(line);
}
if (activeBlend) blendEntries.push(activeBlend);

function fieldValue(lines, name) {
    const prefix = name + ':';
    const line = lines.find(item => item.trimStart().startsWith(prefix));
    if (!line) return null;
    const split = line.split(' = ');
    return split.length > 1 ? split.slice(1).join(' = ').trim() : null;
}
function numericField(lines, name) {
    const value = fieldValue(lines, name);
    return value === null ? null : Number(value);
}
function listHashes(lines, name) {
    const index = lines.findIndex(item => item.includes(name + ':'));
    if (index < 0) return [];
    const gathered = lines.slice(index, index + 4).join(' ');
    return [...gathered.matchAll(/0x([0-9a-f]{1,8})/g)].map(match => match[1].padStart(8, '0'));
}
function parseEvents(lines) {
    const events = [];
    let active = null;
    function flush() {
        if (!active) return;
        const body = active.lines;
        const type = active.type;
        const event = {
            eventKey: active.key,
            type,
            mStartFrame: numericField(body, 'mStartFrame'),
            mEndFrame: numericField(body, 'mEndFrame'),
            mShowSubmeshList: listHashes(body, 'mShowSubmeshList').map(hash => ({ hash: '0x' + hash, name: submeshNamesByHash.get(hash) || null })),
            mHideSubmeshList: listHashes(body, 'mHideSubmeshList').map(hash => ({ hash: '0x' + hash, name: submeshNamesByHash.get(hash) || null })),
            mEffectKey: fieldValue(body, 'mEffectKey'),
            mBoneName: fieldValue(body, 'mBoneName'),
            mSoundName: fieldValue(body, 'mSoundName'),
            mStopAnimationName: fieldValue(body, 'mStopAnimationName'),
            mIsLoop: fieldValue(body, 'mIsLoop'),
            mScalePlaySpeedWithAnimation: fieldValue(body, 'mScalePlaySpeedWithAnimation'),
            rawFields: body.map(line => line.trim()).filter(Boolean),
        };
        if (event.mBoneName) {
            const hash = event.mBoneName.replace(/^0x/, '').padStart(8, '0');
            event.mBoneNameResolved = boneNamesByHash.get(hash) || null;
        }
        if (event.mEffectKey) event.mEffectResolution = resolveEffect(event.mEffectKey);
        events.push(event);
        active = null;
    }
    for (const line of lines) {
        const indent = line.length - line.trimStart().length;
        const trimmed = line.trim();
        if (indent === 20 && trimmed.includes(' = ') && trimmed.includes('EventData')) {
            flush();
            const [keyPart, typePart] = trimmed.split(' = ');
            active = { key: keyPart, type: typePart.split(' ')[0], lines: [line] };
            if (typePart.includes('{ }')) flush();
            continue;
        }
        if (active) {
            if (indent === 20 && trimmed === '}') {
                flush();
            } else {
                active.lines.push(line);
            }
        }
    }
    flush();
    return events;
}
function clipId(sourcePath) {
    return sourcePath ? sourcePath.split('/').pop().replace(/\.anm$/i, '') : null;
}
function directionalBase(id) {
    const match = id && id.match(/^(.*?)(?:_)?(-179|-90|90|179|180)$/);
    return match ? { parent: match[1].replace(/_$/, ''), degrees: Number(match[2]) } : null;
}
function parentTransition(id) {
    if (!id) return null;
    const match = id.match(/^(.*)_(to_idle|to_run|to_passiveidle|to_passiverun)$/);
    return match ? match[1] : null;
}
function classify(id) {
    if (!id) return { category: 'unknown', slot: null, phase: null };
    if (/^spell1(?:_|$)/.test(id)) return { category: 'ability', slot: 'Q', phase: id.includes('to_') ? 'exit-transition' : id === 'spell1' ? 'initial' : id.includes('_b') ? 'follow-up-b' : id.includes('_c') ? 'follow-up-c' : 'directional-variant' };
    if (/^spell2(?:_|$)/.test(id)) return { category: id.includes('to_') ? 'transition' : 'ability', slot: 'W', phase: id.includes('to_') ? 'exit-transition' : 'activation' };
    if (/^spell3(?:_|$)/.test(id)) return { category: id.includes('to_') ? 'transition' : 'ability', slot: 'E', phase: id.includes('dash') ? 'dash' : 'exit-transition' };
    if (/^spell4b?(?:_|$)/.test(id)) return { category: id.includes('to_') ? 'transition' : 'ability', slot: 'R', phase: id.startsWith('spell4b') ? (id.includes('to_') ? 'exit-transition' : 'follow-up' ) : (id.includes('to_') ? 'exit-transition' : 'initial') };
    if (/^recall/.test(id)) return { category: 'recall', slot: null, phase: 'excluded-by-request' };
    if (/^(joke|dance|taunt|laugh)/.test(id)) return { category: 'emote', slot: null, phase: id.startsWith('joke') ? id.includes('loop') ? 'loop' : 'start-or-transition' : 'loop-or-cast' };
    if (/^(attack|passive_attack|critical)/.test(id)) return { category: 'attack', slot: null, phase: 'attack-or-crit' };
    if (/^(death|respawn|knockup|stun)/.test(id)) return { category: 'combat-state', slot: null, phase: id };
    if (/^(idle|passive_idle)/.test(id)) return { category: 'idle', slot: null, phase: id };
    if (/^(run|into_run|passive_run|turn|passive_to_run)/.test(id)) return { category: 'locomotion', slot: null, phase: id };
    if (/homeguard/.test(id)) return { category: 'homeguard', slot: null, phase: id };
    if (/^passive/.test(id)) return { category: 'passive-state-or-transition', slot: null, phase: id };
    if (id.includes('_to_')) return { category: 'transition', slot: null, phase: id };
    return { category: 'other', slot: null, phase: id };
}

const clips = rawClips.map(raw => {
    const fileLine = raw.lines.find(line => line.includes('mAnimationFilePath: file = '));
    const fileMatch = fileLine && fileLine.match(/0x([0-9a-f]{1,16})/);
    const fileHash = fileMatch ? fileMatch[1].padStart(16, '0') : null;
    const sourcePath = fileHash ? assetPathsByHash.get(fileHash) || null : null;
    const id = clipId(sourcePath);
    const timingPath = sourcePath ? path.join(studyDir, id + '.anm') : null;
    let durationSeconds = null, nativeFps = null, nativeFrameStepSeconds = null;
    if (timingPath && fs.existsSync(timingPath)) {
        const anm = fs.readFileSync(timingPath);
        const magic = anm.subarray(0, 8).toString();
        if (anm.length >= 44 && magic === 'r3d2canm') {
            durationSeconds = anm.readFloatLE(36);
            nativeFps = anm.readFloatLE(40);
            nativeFrameStepSeconds = nativeFps > 0 ? 1 / nativeFps : null;
        } else if (anm.length >= 56 && magic === 'r3d2anmd') {
            const frameCount = anm.readUInt32LE(32);
            nativeFrameStepSeconds = anm.readFloatLE(36);
            nativeFps = nativeFrameStepSeconds > 0 ? 1 / nativeFrameStepSeconds : null;
            durationSeconds = Math.max(0, frameCount - 1) * nativeFrameStepSeconds;
        }
    }
    const events = parseEvents(raw.lines);
    const mTickDuration = numericField(raw.lines, 'mTickDuration');
    const eventTickDuration = mTickDuration ?? nativeFrameStepSeconds;
    for (const event of events) {
        const startFrame = event.mStartFrame === null ? 0 : event.mStartFrame;
        const endFrame = event.mEndFrame === null ? null : event.mEndFrame;
        if (event.type === 'SubmeshVisibilityEventData') {
            event.rawFrameWindow = { mStartFrame: event.mStartFrame, mEndFrame: event.mEndFrame };
            event.visibilityDirectives = [
                ...event.mShowSubmeshList.map(submesh => ({ action: 'show', submesh, startFrame, endFrame })),
                ...event.mHideSubmeshList.map(submesh => ({ action: 'hide', submesh, startFrame, endFrame })),
            ].map(directive => ({
                ...directive,
                startSeconds: eventTickDuration === null ? null : directive.startFrame * eventTickDuration,
                endSeconds: directive.endFrame === null
                    ? durationSeconds
                    : eventTickDuration === null ? null : directive.endFrame * eventTickDuration,
                tickDurationSeconds: eventTickDuration,
                tickDurationSource: mTickDuration === null ? 'native ANM frame interval' : 'AtomicClipData.mTickDuration',
                endpointSemantics: 'source mStartFrame/mEndFrame retained separately; computed time is a frame-boundary interpretation',
            }));
        }
    }
    const direction = directionalBase(id);
    const transitionParent = parentTransition(id);
    return {
        graphClipKey: raw.key,
        graphNodeType: 'AtomicClipData',
        sourceFileHash: fileHash ? '0x' + fileHash : null,
        sourcePath,
        clipId: id,
        ...classify(id),
        directionalParentClipId: direction ? direction.parent : null,
        directionDegrees: direction ? direction.degrees : null,
        transitionParentClipId: transitionParent,
        excludedFromBuildByRequest: classify(id).category === 'recall',
        durationSeconds,
        nativeFps,
        nativeFrameStepSeconds,
        mTickDuration,
        eventTickDurationSeconds: eventTickDuration,
        mTrackDataName: fieldValue(raw.lines, 'mTrackDataName'),
        mFlags: fieldValue(raw.lines, 'mFlags'),
        events,
    };
});
const clipByKey = new Map(clips.map(clip => [clip.graphClipKey, clip]));
const runtimeGraphNodes = graphNodesRaw.map(raw => {
    const node = {
        graphClipKey: raw.key,
        graphNodeType: raw.type,
        mTrackDataName: fieldValue(raw.lines, 'mTrackDataName'),
        mFlags: fieldValue(raw.lines, 'mFlags'),
        mTickDuration: numericField(raw.lines, 'mTickDuration'),
        updater: null,
        references: [],
        pairs: [],
        clipNameList: [],
        condition: null,
        events: parseEvents(raw.lines),
    };
    const updaterLine = raw.lines.find(line => line.trimStart().startsWith('Updater: pointer = '));
    if (updaterLine) node.updater = updaterLine.trim().slice('Updater: pointer = '.length).replace(/\s*\{.*$/, '');
    for (const line of raw.lines) {
        const match = line.match(/^\s*(mTrueConditionClipName|mFalseConditionClipName|mClipName): hash = (0x[0-9a-f]+)\s*$/);
        if (match) node.references.push({ field: match[1], graphClipKey: match[2] });
    }
    const clipListLine = raw.lines.find(line => line.includes('mClipNameList:'));
    if (clipListLine) {
        const body = raw.lines.slice(raw.lines.indexOf(clipListLine), raw.lines.indexOf(clipListLine) + 3).join(' ');
        node.clipNameList = [...body.matchAll(/0x([0-9a-f]{1,8})/g)].map(match => '0x' + match[1]);
    }
    let pair = null;
    function pushPair() { if (pair) node.pairs.push(pair); pair = null; }
    for (const line of raw.lines) {
        const indent = line.length - line.trimStart().length;
        const trimmed = line.trim();
        if (indent >= 16 && /^(ParametricPairData|SelectorPairData|ConditionFloatPairData) \{$/.test(trimmed)) {
            pushPair();
            pair = { pairType: trimmed.slice(0, trimmed.indexOf(' ')), graphClipKey: null, mValue: null, mProbability: null };
            continue;
        }
        if (pair) {
            const clipMatch = trimmed.match(/^mClipName: hash = (0x[0-9a-f]+)$/);
            if (clipMatch) pair.graphClipKey = clipMatch[1];
            const valueMatch = trimmed.match(/^mValue: f32 = (.+)$/);
            if (valueMatch) pair.mValue = Number(valueMatch[1]);
            const probabilityMatch = trimmed.match(/^mProbability: f32 = (.+)$/);
            if (probabilityMatch) pair.mProbability = Number(probabilityMatch[1]);
            if (indent >= 16 && trimmed === '}') pushPair();
        }
    }
    pushPair();
    for (const ref of node.references) ref.resolved = clipByKey.get(ref.graphClipKey)?.clipId || null;
    for (const item of node.clipNameList) item;
    node.pairs = node.pairs.map(item => ({
        ...item,
        resolvedClipId: item.graphClipKey ? clipByKey.get(item.graphClipKey)?.clipId || null : null,
    }));
    node.clipNameList = node.clipNameList.map(graphClipKey => ({
        graphClipKey,
        resolvedClipId: clipByKey.get(graphClipKey)?.clipId || null,
    }));
    if (node.graphNodeType === 'ConditionBoolClipData') {
        node.condition = {
            trueClip: node.references.find(ref => ref.field === 'mTrueConditionClipName') || null,
            falseClip: node.references.find(ref => ref.field === 'mFalseConditionClipName') || null,
            changeAnimationMidPlay: fieldValue(raw.lines, 'mChangeAnimationMidPlay'),
        };
    }
    return node;
});
const nodeByKey = new Map(runtimeGraphNodes.map(node => [node.graphClipKey, node]));
for (const node of runtimeGraphNodes) {
    const clip = clipByKey.get(node.graphClipKey);
    if (clip) {
        node.clipId = clip.clipId;
        node.sourcePath = clip.sourcePath;
        node.slot = clip.slot;
        node.phase = clip.phase;
        node.excludedFromBuildByRequest = clip.excludedFromBuildByRequest;
    }
}
function descendantAtomicKeys(graphKey, seen = new Set()) {
    if (!graphKey || seen.has(graphKey)) return [];
    if (clipByKey.has(graphKey)) return [graphKey];
    const node = nodeByKey.get(graphKey);
    if (!node) return [];
    const nextSeen = new Set(seen);
    nextSeen.add(graphKey);
    const children = [
        ...node.references.map(ref => ref.graphClipKey),
        ...node.pairs.map(pair => pair.graphClipKey),
        ...node.clipNameList.map(item => item.graphClipKey),
    ].filter(Boolean);
    return [...new Set(children.flatMap(key => descendantAtomicKeys(key, nextSeen)))];
}
const timeBlendTable = blendEntries.filter(item => item.type === 'TimeBlendData').map(item => ({
    blendTableKey: item.blendTableKey,
    mTime: numericField(item.lines, 'mTime'),
    mBlendTime: numericField(item.lines, 'mBlendTime'),
}));
const transitionBlendTable = blendEntries.filter(item => item.type === 'TransitionClipBlendData').map(item => {
    const targetMatch = fieldValue(item.lines, 'mClipName');
    const targetKey = targetMatch && targetMatch.startsWith('0x') ? targetMatch : null;
    const target = targetKey ? clipByKey.get(targetKey) : null;
    const targetNode = targetKey ? nodeByKey.get(targetKey) : null;
    const targetAtomicKeys = targetKey ? descendantAtomicKeys(targetKey) : [];
    return {
        blendTableKey: item.blendTableKey,
        mTime: numericField(item.lines, 'mTime'),
        mBlendTime: numericField(item.lines, 'mBlendTime'),
        mClipName: targetKey,
        targetClipId: target?.clipId || null,
        targetSourcePath: target?.sourcePath || null,
        targetGraphNodeType: targetNode?.graphNodeType || null,
        targetAtomicGraphClipKeys: targetAtomicKeys,
        targetAtomicClipIds: targetAtomicKeys.map(key => clipByKey.get(key)?.clipId).filter(Boolean),
        fields: item.lines.map(line => line.trim()).filter(line => line && line !== '}'),
    };
});
const trackData = rawTracks.map(raw => ({
    trackDataHash: raw.key,
    trackType: raw.type,
    mPriority: fieldValue(raw.lines, 'mPriority'),
    mBlendMode: fieldValue(raw.lines, 'mBlendMode'),
}));
const aliases = new Map();
for (const clip of clips) {
    if (!clip.clipId) continue;
    if (!aliases.has(clip.clipId)) aliases.set(clip.clipId, []);
    aliases.get(clip.clipId).push(clip.graphClipKey);
}
const eventTypeCounts = {};
const effectKeyResolutions = new Map();
for (const node of runtimeGraphNodes) for (const event of node.events) {
    eventTypeCounts[event.type] = (eventTypeCounts[event.type] || 0) + 1;
    if (event.mEffectKey && !effectKeyResolutions.has(event.mEffectKey)) {
        effectKeyResolutions.set(event.mEffectKey, event.mEffectResolution || resolveEffect(event.mEffectKey));
    }
}
skinDefaults.effectKeyResolutions = [...effectKeyResolutions].map(([effectKey, resolution]) => ({ effectKey, ...resolution }));
skinDefaults.resourceResolverEntries = resourceResolver.size;
const unresolvedGraphAssets = clips.filter(clip => !clip.sourcePath).map(clip => ({ graphClipKey: clip.graphClipKey, sourceFileHash: clip.sourceFileHash }));
const missingExtractedFiles = [...new Set(clips.filter(clip => clip.clipId && !fs.existsSync(path.join(studyDir, clip.clipId + '.anm'))).map(clip => clip.clipId))];
const result = {
    schemaVersion: 1,
    evidence: {
        nativeGraph: 'data/characters/gwen/animations/skin0.bin from Gwen.wad.client',
        readableGraph: 'animation-skin0_named.rito',
        fileNameCrosswalk: 'Rose/_internal/injection/tools/hashes.game.txt',
        submeshNameCrosswalk: 'Gwen skin0 SKN section names, verified against FNV-1a hashes',
    },
    counts: {
        graphClipKeys: clips.length,
        uniqueAnimationFiles: new Set(clips.map(clip => clip.sourcePath).filter(Boolean)).size,
        aliases: [...aliases.values()].filter(keys => keys.length > 1).length,
        submeshVisibilityEvents: clips.reduce((sum, clip) => sum + clip.events.filter(event => event.type === 'SubmeshVisibilityEventData').length, 0),
        graphRuntimeNodes: runtimeGraphNodes.length,
        parametricNodes: runtimeGraphNodes.filter(node => node.graphNodeType === 'ParametricClipData').length,
        selectorNodes: runtimeGraphNodes.filter(node => node.graphNodeType === 'SelectorClipData').length,
        sequencerNodes: runtimeGraphNodes.filter(node => node.graphNodeType === 'SequencerClipData').length,
        conditionNodes: runtimeGraphNodes.filter(node => node.graphNodeType.startsWith('Condition')).length,
        trackDataNodes: trackData.length,
        timeBlendEntries: timeBlendTable.length,
        transitionBlendEntries: transitionBlendTable.length,
        eventTypeCounts,
    },
    coverage: {
        graphClipKeys: clips.length,
        graphFileReferencesResolved: clips.length - unresolvedGraphAssets.length,
        unresolvedGraphAssets,
        uniqueAnimationFiles: new Set(clips.map(clip => clip.sourcePath).filter(Boolean)).size,
        missingExtractedAnimationFiles: missingExtractedFiles,
    },
    submeshHashes: Object.fromEntries([...submeshNamesByHash].map(([hash, name]) => ['0x' + hash, name])),
    skinDefaults,
    aliases: [...aliases].filter(([, keys]) => keys.length > 1).map(([clipId, graphClipKeys]) => ({ clipId, graphClipKeys })),
    directionalParents: clips.filter(clip => clip.directionalParentClipId).map(clip => ({
        clipId: clip.clipId, graphClipKey: clip.graphClipKey,
        parentClipId: clip.directionalParentClipId, directionDegrees: clip.directionDegrees,
    })),
    stagedAbilities: {
        Q: clips.filter(clip => clip.slot === 'Q').map(clip => ({ clipId: clip.clipId, graphClipKey: clip.graphClipKey, phase: clip.phase })),
        W: clips.filter(clip => clip.slot === 'W').map(clip => ({ clipId: clip.clipId, graphClipKey: clip.graphClipKey, phase: clip.phase })),
        E: clips.filter(clip => clip.slot === 'E').map(clip => ({ clipId: clip.clipId, graphClipKey: clip.graphClipKey, phase: clip.phase })),
        R: clips.filter(clip => clip.slot === 'R').map(clip => ({ clipId: clip.clipId, graphClipKey: clip.graphClipKey, phase: clip.phase })),
    },
    graphComposition: {
        clipDataMap: runtimeGraphNodes,
        trackDataMap: trackData,
        timeBlendTable,
        transitionBlendTable,
        transitionKeySemantics: 'The graph preserves opaque u64 blend-table keys verbatim; each TransitionClipBlendData target mClipName is resolved to its graph clip key/path. The key is not interpreted as a source/destination pair.',
    },
    runtimeGraphNodes,
    clips,
};
const output = path.join(studyDir, 'graph_inventory.json');
fs.writeFileSync(output, JSON.stringify(result, null, 2));
console.log(`Graph index: ${clips.length} clip keys, ${result.counts.uniqueAnimationFiles} unique ANMs, ${result.counts.submeshVisibilityEvents} submesh visibility events -> ${output}`);
