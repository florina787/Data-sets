// Renders film.html frame by frame (deterministic, smooth at any machine speed) into
// site/media/film.mp4, film.webm, film.gif and film-poster.jpg.
//   node site/tools/film/render.mjs [--stills 1.2,5,9.5]   (stills only, for checking)
// Needs `playwright` resolvable and ffmpeg.
import { createRequire } from "node:module";
import { spawn, execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const require = createRequire(path.join(process.cwd(), "noop.js"));
const { chromium } = require("playwright");
const here = import.meta.dirname, media = path.resolve(here, "../../media");
const FPS = 30;
const stillsArg = process.argv.indexOf("--stills");

const browser = await chromium.launch({ args: ["--allow-file-access-from-files", "--autoplay-policy=no-user-gesture-required"] });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
await page.goto("file://" + path.join(here, "film.html"));
await page.evaluate(() => window.ready);
const duration = await page.evaluate(() => window.DURATION);

if (stillsArg > 0) {
  const outDir = process.argv[stillsArg + 2] || "/tmp";
  for (const t of process.argv[stillsArg + 1].split(",").map(Number)) {
    await page.evaluate((x) => window.render(x), t);
    await page.screenshot({ path: path.join(outDir, `still-${t}.png`) });
  }
  console.log("stills written to", outDir, "duration", duration.toFixed(2));
  await browser.close();
  process.exit(0);
}

const frames = Math.round(duration * FPS);
const raw = path.join(media, ".film-raw.mp4");
const ff = spawn("ffmpeg", ["-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "-",
  "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", raw], { stdio: ["pipe", "inherit", "inherit"] });
for (let i = 0; i < frames; i++) {
  await page.evaluate((x) => window.render(x), i / FPS);
  const buf = await page.screenshot({ type: "jpeg", quality: 92 });
  if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
  if (i % 60 === 0) console.log(`frame ${i}/${frames}`);
}
ff.stdin.end();
await new Promise((r) => ff.on("close", r));
await browser.close();

const run = (...a) => execFileSync("ffmpeg", ["-loglevel", "error", "-y", ...a], { stdio: "inherit" });
run("-i", raw, "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart", path.join(media, "film.mp4"));
run("-i", raw, "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "38", "-row-mt", "1", path.join(media, "film.webm"));
const pal = path.join(media, ".film-pal.png");
run("-i", raw, "-vf", "fps=15,scale=720:-1:flags=lanczos,palettegen=max_colors=160:stats_mode=diff", pal);
run("-i", raw, "-i", pal, "-lavfi", "fps=15,scale=720:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle", path.join(media, "film.gif"));
run("-ss", "1.5", "-i", raw, "-frames:v", "1", "-q:v", "3", path.join(media, "film-poster.jpg"));
fs.unlinkSync(raw); fs.unlinkSync(pal);
for (const f of ["film.mp4", "film.webm", "film.gif", "film-poster.jpg"]) console.log(f, (fs.statSync(path.join(media, f)).size / 1e6).toFixed(2), "MB");
console.log("duration", duration.toFixed(2), "s");
