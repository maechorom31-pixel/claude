const zlib = require('zlib');
const fs = require('fs');
const path = require('path');

function crc32(buf) {
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < buf.length; i++) {
    crc = crc ^ buf[i];
    for (let j = 0; j < 8; j++) crc = (crc >>> 1) ^ (0xEDB88320 & -(crc & 1));
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length, 0);
  const t = Buffer.from(type);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(Buffer.concat([t, data])), 0);
  return Buffer.concat([len, t, data, crc]);
}
function writePng(filePath, W, H, draw) {
  const px = Buffer.alloc(W * H * 4);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const c = draw(x, y, W, H);
    const i = (y * W + x) * 4;
    px[i] = c[0]; px[i+1] = c[1]; px[i+2] = c[2]; px[i+3] = c[3];
  }
  const row = W * 4 + 1;
  const raw = Buffer.alloc(H * row);
  for (let y = 0; y < H; y++) {
    raw[y * row] = 0;
    px.copy(raw, y * row + 1, y * W * 4, (y + 1) * W * 4);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(W, 0); ihdr.writeUInt32BE(H, 4);
  ihdr[8] = 8; ihdr[9] = 6;
  const png = Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
    chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0))
  ]);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, png);
}

function spiritPaint(x, y, W, H) {
  const cx = W / 2, cy = H / 2;
  const dx = x - cx, dy = y - cy;
  const r = Math.sqrt(dx * dx + dy * dy);
  const outerR = Math.min(W, H) * 0.46;
  const innerR = Math.min(W, H) * 0.28;
  if (r > outerR) return [0, 0, 0, 0];
  if (r > outerR - 2) {
    const a = Math.max(0, Math.min(1, (outerR - r) / 2));
    return [240, 196, 132, Math.round(255 * a * 0.7)];
  }
  if (r > innerR) {
    const t = (outerR - r) / (outerR - innerR);
    const cr = Math.round(248 - 8 * (1 - t));
    const cg = Math.round(220 - 30 * (1 - t));
    const cb = Math.round(176 - 60 * (1 - t));
    return [cr, cg, cb, 235];
  }
  const t = r / innerR;
  const cr = Math.round(252 - 8 * t);
  const cg = Math.round(238 - 24 * t);
  const cb = Math.round(206 - 40 * t);
  return [cr, cg, cb, 250];
}

const out = process.argv[2] || 'assets/icons';
writePng(path.join(out, 'app.png'), 256, 256, spiritPaint);
writePng(path.join(out, 'tray.png'), 32, 32, spiritPaint);
writePng(path.join(out, 'tray@2x.png'), 64, 64, spiritPaint);
console.log('icons written to', out);
