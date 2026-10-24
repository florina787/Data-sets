// Generates every raster brand asset from the single SVG source in src/brand/catSvg.mjs.
import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";
import pngToIco from "png-to-ico";
import { catSvg, PALETTE } from "../src/brand/catSvg.mjs";

const root = path.resolve(import.meta.dirname, "..");
const assets = path.join(root, "assets");
const pub = path.join(root, "public");
const build = path.join(root, "build");
for (const d of [assets, pub, build]) fs.mkdirSync(d, { recursive: true });

const icon = catSvg({ background: PALETTE.white, padding: 20 });
const mark = catSvg();
fs.writeFileSync(path.join(assets, "veena-cat.svg"), mark);
fs.writeFileSync(path.join(assets, "veena-icon.svg"), icon);
fs.writeFileSync(path.join(pub, "favicon.svg"), icon);

const png = (svg, size) => sharp(Buffer.from(svg), { density: 384 }).resize(size, size).png().toBuffer();

const sizes = [16, 24, 32, 48, 64, 128, 256, 512, 1024];
const bufs = {};
for (const s of sizes) {
  bufs[s] = await png(icon, s);
  fs.writeFileSync(path.join(assets, `icon-${s}.png`), bufs[s]);
}
fs.writeFileSync(path.join(build, "icon.png"), bufs[1024]);
fs.writeFileSync(path.join(build, "icon.ico"), await pngToIco([16, 24, 32, 48, 64, 128, 256].map((s) => bufs[s])));
fs.writeFileSync(path.join(pub, "favicon-32.png"), bufs[32]);

// Installer sidebar (NSIS: 164x314 BMP-compatible PNG) and DMG background.
const wordmark = (w, h, catSize, y) => `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}">
  <rect width="100%" height="100%" fill="${PALETTE.warmWhite}"/>
  <g transform="translate(${(w - catSize) / 2}, ${y}) scale(${catSize / 256})">${mark.replace(/^<svg[^>]*>|<\/svg>$/g, "")}</g>
  <text x="50%" y="${y + catSize + 34}" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif" font-size="26" font-weight="700" fill="${PALETTE.darkBrown}" text-anchor="middle">veena.ai</text>
  <text x="50%" y="${y + catSize + 58}" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif" font-size="11" fill="${PALETTE.caramel}" text-anchor="middle">Your intelligent conversation companion.</text>
</svg>`;
// NSIS only accepts 24-bit BMP for its wizard images.
async function writeBmp(svg, file) {
  const { data, info } = await sharp(Buffer.from(svg)).flatten({ background: PALETTE.warmWhite }).removeAlpha().raw().toBuffer({ resolveWithObject: true });
  const rowSize = Math.ceil((info.width * 3) / 4) * 4;
  const out = Buffer.alloc(54 + rowSize * info.height);
  out.write("BM", 0);
  out.writeUInt32LE(out.length, 2);
  out.writeUInt32LE(54, 10);
  out.writeUInt32LE(40, 14);
  out.writeInt32LE(info.width, 18);
  out.writeInt32LE(info.height, 22);
  out.writeUInt16LE(1, 26);
  out.writeUInt16LE(24, 28);
  out.writeUInt32LE(rowSize * info.height, 34);
  for (let y = 0; y < info.height; y++) {
    for (let x = 0; x < info.width; x++) {
      const src = (y * info.width + x) * 3;
      const dst = 54 + (info.height - 1 - y) * rowSize + x * 3;
      out[dst] = data[src + 2];
      out[dst + 1] = data[src + 1];
      out[dst + 2] = data[src];
    }
  }
  fs.writeFileSync(file, out);
}
await writeBmp(wordmark(164, 314, 120, 60), path.join(build, "installerSidebar.bmp"));
await sharp(Buffer.from(wordmark(540, 380, 160, 70))).png().toFile(path.join(build, "background.png"));
console.log("brand assets written to assets/, public/ and build/");
