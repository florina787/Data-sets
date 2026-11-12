// Turns Electron's raw desktopCapturer sources into what the picker shows. Pure functions (no Electron
// import) so they are unit-tested. A source is only offered for sharing when it can produce frames:
// minimized windows, windows on another virtual desktop and protected/cloaked system windows come back
// with an empty or single-colour thumbnail on Windows, and capturing them yields black frames.

export interface RawSource {
  id: string;
  name: string;
  display_id?: string;
  thumbnailEmpty: boolean;
  /** BGRA pixels of the thumbnail (Electron NativeImage.toBitmap()), or null when empty. */
  bitmap: Uint8Array | null;
}

export interface DisplayInfo {
  id: number;
  width: number;
  height: number;
  scaleFactor: number;
  primary: boolean;
}

export interface PickerSource {
  id: string;
  name: string;
  kind: "screen" | "window";
  previewable: boolean;
  /** Why a source has no preview / cannot be shared (shown to the user). */
  note: string | null;
}

/** True when every sampled pixel has (almost) the same colour: a black, white or transparent thumbnail. */
export function isBlankBitmap(px: Uint8Array | null, samples = 400): boolean {
  if (!px || px.length < 4) return true;
  const n = px.length / 4;
  const step = Math.max(1, Math.floor(n / samples));
  let min = 255 * 4,
    max = 0;
  for (let i = 0; i < n; i += step) {
    const o = i * 4;
    const v = px[o] + px[o + 1] + px[o + 2] + (px[o + 3] < 8 ? 0 : 255); // transparent counts as one colour
    if (v < min) min = v;
    if (v > max) max = v;
  }
  return max - min < 12;
}

export function describeSources(raw: RawSource[], displays: DisplayInfo[], ownTitles: string[], platform: string): PickerSource[] {
  const screens = raw.filter((s) => s.id.startsWith("screen:"));
  const out: PickerSource[] = [];
  screens.forEach((s, i) => {
    const d = displays.find((x) => String(x.id) === s.display_id) ?? (screens.length === displays.length ? displays[i] : undefined);
    const label = d
      ? `Display ${i + 1} · ${Math.round(d.width * d.scaleFactor)}×${Math.round(d.height * d.scaleFactor)}${d.primary ? " (primary)" : ""}`
      : s.name || `Screen ${i + 1}`;
    const blank = s.thumbnailEmpty || isBlankBitmap(s.bitmap);
    out.push({
      id: s.id,
      name: label,
      kind: "screen",
      // A screen is always offered; a blank preview usually means missing permission (macOS) or a locked screen.
      previewable: !blank,
      note: blank
        ? platform === "darwin"
          ? "No preview: allow VEENA in System Settings → Privacy & Security → Screen Recording, then reopen VEENA."
          : "No preview available for this display right now."
        : null,
    });
  });
  for (const s of raw) {
    if (s.id.startsWith("screen:")) continue;
    const name = (s.name || "").trim();
    if (!name || ownTitles.includes(name)) continue; // untitled helper windows and VEENA itself are never offered
    const blank = s.thumbnailEmpty || isBlankBitmap(s.bitmap);
    out.push({
      id: s.id,
      name,
      kind: "window",
      previewable: !blank,
      note: blank ? "No preview: the window is minimized, on another desktop, or protected from capture. Restore it and refresh." : null,
    });
  }
  return out;
}
