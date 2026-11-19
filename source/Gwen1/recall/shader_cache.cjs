// Resolve League material defines through the installed DX11 ShaderCache WAD.
const { openWad, xxh64 } = require('./game_wad.cjs');

function readToc(wad, objectPath) {
  const tocPath = (objectPath.endsWith('.ps-dx11') || objectPath.endsWith('.vs-dx11'))
    ? objectPath.toLowerCase()
    : objectPath.toLowerCase() + '.ps-dx11';
  const data = wad.readEntry(tocPath);
  if (!data) return null;
  let offset = 0;
  const string = () => {
    const length = data.readUInt32LE(offset);
    offset += 4;
    const value = data.toString('utf8', offset, offset + length);
    offset += length;
    return value;
  };
  const magic = string();
  if (magic !== 'TOC3.0') throw new Error('Unexpected shader TOC magic at ' + tocPath);
  const shaderCount = data.readUInt32LE(offset); offset += 4;
  const baseCount = data.readUInt32LE(offset); offset += 4;
  const bundledCount = data.readUInt32LE(offset); offset += 4;
  const shaderType = data.readUInt32LE(offset); offset += 4;
  if (string() !== 'baseDefines') throw new Error('Shader TOC is missing baseDefines');
  const baseDefines = [];
  for (let i = 0; i < baseCount; i++) baseDefines.push([string(), string()]);
  if (string() !== 'shaders') throw new Error('Shader TOC is missing shader index');
  const hashes = [];
  for (let i = 0; i < shaderCount; i++) { hashes.push(data.readBigUInt64LE(offset)); offset += 8; }
  const ids = [];
  for (let i = 0; i < shaderCount; i++) { ids.push(data.readUInt32LE(offset)); offset += 4; }
  if (offset !== data.length) throw new Error('Shader TOC has trailing or unread data');
  return { tocPath, shaderCount, bundledCount, shaderType, baseDefines, hashes, ids };
}

function asPairs(defines) {
  if (Array.isArray(defines)) return defines.map(String);
  return Object.entries(defines).map(([name, value]) => {
    if (typeof value === 'boolean') value = value ? '1' : '0';
    return value === '' || value === null ? name : name + '=' + value;
  });
}

function resolveStage(wad, objectPath, stage, defines, onBytecode) {
  const fullPath = objectPath.toLowerCase().replace(/\.(?:ps|vs)-dx11$/, '') + '.' + stage + '-dx11';
  const toc = readToc(wad, fullPath);
  if (!toc) return { stage, path: fullPath, status: 'missing-toc' };
  const requested = new Set(asPairs(defines));
  const filtered = toc.baseDefines
    .map(([name, value]) => value === '' ? name : name + '=' + value)
    .filter(define => requested.has(define))
    .sort()
    .join('');
  const variantHash = xxh64(filtered);
  const index = toc.hashes.findIndex(value => value === variantHash);
  if (index < 0) {
    return {
      stage, path: fullPath, status: 'variant-missing',
      variantHash: variantHash.toString(), filtered, baseDefineCount: toc.baseDefines.length,
      availableVariants: toc.shaderCount,
    };
  }
  const shaderId = toc.ids[index];
  const bundleIndex = 100 * Math.floor(shaderId / 100);
  const bundle = wad.readEntry(fullPath + '_' + bundleIndex);
  if (!bundle) return { stage, path: fullPath, status: 'missing-bundle', shaderId, bundleIndex, filtered };
  let offset = 0;
  let code = null;
  for (let i = 0; i <= shaderId % 100; i++) {
    if (offset + 4 > bundle.length) throw new Error('Truncated shader bundle at ' + fullPath);
    const length = bundle.readUInt32LE(offset);
    offset += 4;
    if (offset + length > bundle.length) throw new Error('Invalid bytecode size in ' + fullPath);
    if (i === shaderId % 100) code = bundle.subarray(offset, offset + length);
    offset += length;
  }
  const magic = code.toString('ascii', 0, 4);
  // The cache can append a terminator to the DXBC container. Check the declared
  // bytes and the actual program's stage, including bundles shared by hashes.
  let expectedStage = false;
  if (magic === 'DXBC' && code.length >= 32) {
    const length = code.readUInt32LE(24), chunks = code.readUInt32LE(28);
    if (length > code.length || 32 + chunks * 4 > length) throw Error('Invalid DXBC directory');
    for (let i = 0; i < chunks; i++) {
      const pos = code.readUInt32LE(32 + 4*i);
      if (pos + 8 > length || pos + 8 + code.readUInt32LE(pos+4) > length) throw Error('Invalid DXBC chunk');
      if (['SHDR','SHEX'].includes(code.toString('ascii',pos,pos+4)) && code.readUInt32LE(pos+4) >= 8) {
        expectedStage = (code.readUInt32LE(pos+8) >>> 16) === (stage === 'vs' ? 1 : 0);
      }
    }
  }
  if (expectedStage && onBytecode) onBytecode(code.subarray(0, code.readUInt32LE(24)));
  return {
    stage, path: fullPath, status: expectedStage ? 'available' : 'unexpected-bytecode',
    variantHash: variantHash.toString(), shaderId, bundleIndex, bytecodeBytes: code.length,
    bytecodeMagic: magic, filtered,
  };
}

function verifyMaterial(wad, material, onPixel) {
  const vertex = resolveStage(wad, material.shaderPath, 'vs', material.defines);
  const pixel = resolveStage(wad, material.shaderPath, 'ps', material.defines, onPixel);
  return { material: material.name ?? material.shaderPath, vertex, pixel, success: vertex.status === 'available' && pixel.status === 'available' };
}

module.exports = { readToc, resolveStage, verifyMaterial };

if (require.main === module) {
  const [wadPath, manifestPath, probeDir] = process.argv.slice(2);
  if (!wadPath || !manifestPath) {
    console.error('Usage: node shader_cache.cjs <ShaderCache.dx11.wad.client> <manifest.json>');
    process.exit(2);
  }
  const wad = openWad(wadPath);
  const manifest = require(require('node:path').resolve(manifestPath));
  const report = manifest.materials.map(material => {
    const probeFiles={'Body/normal':'body.dxbc','Scissors/normal':'weapon.dxbc','Doll/normal':'doll.dxbc'};
    const solid = probeFiles[material.name] && !material.defines.COLORPALETTE_DEFAULT;
    const dump = probeDir && solid ? code => {
      const filename = probeFiles[material.name];
      require('node:fs').writeFileSync(require('node:path').join(probeDir,filename),code);
    } : undefined;
    return verifyMaterial(wad,material,dump);
  });
  console.log(JSON.stringify(report, null, 2));
  if (report.some(material => !material.success)) process.exitCode = 1;
}
