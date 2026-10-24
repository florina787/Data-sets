// User-selected screen/window capture. The user must pick a source in VEENA's
// picker; the main process refuses getDisplayMedia without that selection.

import { bridge } from "./bridge";

export interface Region {
  x: number; // 0..1 fractions of the video frame
  y: number;
  w: number;
  h: number;
}

export async function startShare(sourceId: string, withAudio: boolean): Promise<MediaStream> {
  await bridge().selectScreenSource(sourceId, withAudio);
  return navigator.mediaDevices.getDisplayMedia({
    video: { frameRate: { ideal: 5, max: 10 } },
    audio: withAudio,
  });
}

export function stopShare(stream: MediaStream | null) {
  stream?.getTracks().forEach((t) => t.stop());
}

/** Grab the current frame as a PNG data URL, optionally cropped to a region. */
export function captureFrame(video: HTMLVideoElement, region?: Region | null, maxSide = 1920): string {
  const vw = video.videoWidth;
  const vh = video.videoHeight;
  if (!vw || !vh) throw new Error("No video frame yet. Wait for the preview to appear.");
  const r = region ?? { x: 0, y: 0, w: 1, h: 1 };
  const sx = Math.round(r.x * vw);
  const sy = Math.round(r.y * vh);
  const sw = Math.max(8, Math.round(r.w * vw));
  const sh = Math.max(8, Math.round(r.h * vh));
  const scale = Math.min(1, maxSide / Math.max(sw, sh));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(sw * scale);
  canvas.height = Math.round(sh * scale);
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(video, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/png");
}

/** 16x16 difference hash of the frame, for skipping unchanged frames. */
export function frameHash(video: HTMLVideoElement): bigint {
  const canvas = document.createElement("canvas");
  canvas.width = 17;
  canvas.height = 16;
  const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
  ctx.drawImage(video, 0, 0, 17, 16);
  const px = ctx.getImageData(0, 0, 17, 16).data;
  return hashFromRGBA(px, 17, 16);
}

export function hashFromRGBA(px: Uint8ClampedArray, w: number, h: number): bigint {
  let bits = 0n;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w - 1; x++) {
      const i = (y * w + x) * 4;
      const j = i + 4;
      const a = px[i] * 0.299 + px[i + 1] * 0.587 + px[i + 2] * 0.114;
      const b = px[j] * 0.299 + px[j + 1] * 0.587 + px[j + 2] * 0.114;
      bits = (bits << 1n) | (b > a ? 1n : 0n);
    }
  }
  return bits;
}

export function hamming(a: bigint, b: bigint): number {
  let x = a ^ b;
  let n = 0;
  while (x) {
    n += Number(x & 1n);
    x >>= 1n;
  }
  return n;
}
