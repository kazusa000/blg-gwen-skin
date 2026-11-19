// Small read-only WAD v3 reader for inspecting installed League resources.
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');

const u64 = value => BigInt.asUintN(64, value);
const rotate = (value, shift) => u64((value << shift) | (value >> (64n - shift)));
const P1 = 11400714785074694791n;
const P2 = 14029467366897019727n;
const P3 = 1609587929392839161n;
const P4 = 9650029242287828579n;
const P5 = 2870177450012600261n;
const round = (value, lane) => u64(rotate(u64(value + lane * P2), 31n) * P1);

function xxh64(value) {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(value);
  let hash = P5;
  let offset = 0;
  if (bytes.length >= 32) {
    const lanes = [u64(P1 + P2), P2, 0n, u64(-P1)];
    while (offset + 32 <= bytes.length) {
      for (let i = 0; i < 4; i++, offset += 8) {
        lanes[i] = round(lanes[i], bytes.readBigUInt64LE(offset));
      }
    }
    hash = lanes.reduce((sum, lane, i) => u64(sum + rotate(lane, [1n, 7n, 12n, 18n][i])), 0n);
    for (const lane of lanes) hash = u64((hash ^ round(0n, lane)) * P1 + P4);
  }
  hash = u64(hash + BigInt(bytes.length));
  while (offset + 8 <= bytes.length) {
    hash = u64(rotate(hash ^ round(0n, bytes.readBigUInt64LE(offset)), 27n) * P1 + P4);
    offset += 8;
  }
  if (offset + 4 <= bytes.length) {
    hash = u64(rotate(hash ^ u64(BigInt(bytes.readUInt32LE(offset)) * P1), 23n) * P2 + P3);
    offset += 4;
  }
  while (offset < bytes.length) hash = u64(rotate(hash ^ u64(BigInt(bytes[offset++]) * P5), 11n) * P1);
  hash = u64((hash ^ (hash >> 33n)) * P2);
  hash = u64((hash ^ (hash >> 29n)) * P3);
  return hash ^ (hash >> 32n);
}

function pathHash(name) {
  return xxh64(Buffer.from(name.toLowerCase()));
}

function openWad(wadPath) {
  const bytes = fs.readFileSync(wadPath);
  if (bytes.toString('ascii', 0, 2) !== 'RW' || bytes[2] !== 3) {
    throw new Error('Expected League WAD v3 at ' + wadPath);
  }
  const count = bytes.readUInt32LE(268);
  if (272 + count * 32 > bytes.length) throw new Error('Invalid WAD index');
  const entries = new Map();
  for (let i = 0; i < count; i++) {
    const at = 272 + 32 * i;
    const key = bytes.readBigUInt64LE(at);
    entries.set(key.toString(16).padStart(16, '0'), {
      key,
      at,
      start: bytes.readUInt32LE(at + 8),
      packedSize: bytes.readUInt32LE(at + 12),
      rawSize: bytes.readUInt32LE(at + 16),
      codec: bytes[at + 20] & 15,
      chunks: bytes[at + 20] >> 4,
      chunkStart: bytes.readUInt16LE(at + 22),
    });
  }

  const unpack = entry => {
    const packed = bytes.subarray(entry.start, entry.start + entry.packedSize);
    let result;
    if (entry.codec === 0) result = packed;
    else if (entry.codec === 3) result = zlib.zstdDecompressSync(packed);
    else if (entry.codec === 4) {
      const champion = path.basename(wadPath).replace(/\.wad(?:\.client)?$/i, '').toLowerCase();
      const tocPath = 'data/final/champions/' + champion + '.wad.subchunktoc';
      const toc = api.readEntry(tocPath);
      if (!toc) throw new Error('Subchunked entry is missing its table ' + tocPath);
      const pieces = [];
      let cursor = 0;
      for (let i = 0; i < entry.chunks; i++) {
        const record = 16 * (entry.chunkStart + i);
        if (record + 8 > toc.length) throw new Error('Subchunk table index is outside its resource');
        const packedLength = toc.readUInt32LE(record);
        const rawLength = toc.readUInt32LE(record + 4);
        const piece = packed.subarray(cursor, cursor + packedLength);
        if (piece.length !== packedLength) throw new Error('Truncated WAD subchunk');
        pieces.push(packedLength === rawLength ? piece : zlib.zstdDecompressSync(piece));
        cursor += packedLength;
      }
      if (cursor !== packed.length) throw new Error('WAD subchunk lengths do not match the entry');
      result = Buffer.concat(pieces);
    } else throw new Error('Unsupported WAD codec ' + entry.codec);
    if (result.length !== entry.rawSize) throw new Error('WAD entry size mismatch');
    return result;
  };

  const api = {
    listEntries() {
      return [...entries.values()].map(entry => ({
        hash: '0x' + entry.key.toString(16),
        offset: entry.start,
        packedSize: entry.packedSize,
        size: entry.rawSize,
        codec: entry.codec,
      }));
    },
    readEntry(nameOrHash) {
      let entry;
      if (typeof nameOrHash === 'bigint') {
        entry = entries.get(nameOrHash.toString(16).padStart(16, '0'));
      } else if (/^0x[0-9a-f]{1,16}$/i.test(nameOrHash)) {
        entry = entries.get(nameOrHash.slice(2).toLowerCase().padStart(16, '0'));
      } else {
        const name = nameOrHash.replaceAll('\\', '/').replace(/^\/+/, '');
        entry = entries.get(pathHash(name).toString(16).padStart(16, '0'));
      }
      if (!entry) return null;
      return unpack(entry);
    },
  };
  return api;
}

module.exports = { openWad, pathHash, xxh64 };

if (require.main === module) {
  const [wadPath, nameOrHash, outputPath] = process.argv.slice(2);
  if (!wadPath || !nameOrHash) {
    console.error('Usage: node game_wad.cjs <wad-path> <entry-path-or-0x-hash> [output-file]');
    process.exit(2);
  }
  const entry = openWad(wadPath).readEntry(nameOrHash);
  if (!entry) throw new Error('WAD entry not found: ' + nameOrHash);
  if (outputPath) fs.writeFileSync(outputPath, entry);
  else process.stdout.write(entry);
}
