// Single source of truth for the VEENA ginger Persian cat.
// Used by the React <CatMark/> (animated, in-app) and by scripts/make-icons.mjs
// (app icon, favicon, installer art), so anatomy and proportions never drift.
// Original artwork: round fluffy Persian face, ginger fur, cream cheeks,
// amber-brown eyes, small rounded ears, symmetrical about x = 128.

export const PALETTE = {
  white: "#FFFFFF",
  warmWhite: "#FCFAF7",
  ivory: "#F7F1E9",
  cream: "#EFE2D2",
  lightBrown: "#D6B79B",
  ginger: "#B87848",
  caramel: "#99613E",
  mediumBrown: "#75462D",
  darkBrown: "#4A2C1C",
  espresso: "#2C1A12",
};

const C = PALETTE;

// Fluffy ruff: a ring of overlapping tufts around the face.
function ruff(cx, cy, radius, tuft, count, fill) {
  let out = "";
  for (let i = 0; i < count; i++) {
    const a = (Math.PI * 2 * i) / count - Math.PI / 2;
    const x = (cx + Math.cos(a) * radius).toFixed(2);
    const y = (cy + Math.sin(a) * radius).toFixed(2);
    out += `<circle cx="${x}" cy="${y}" r="${tuft}" fill="${fill}"/>`;
  }
  return out;
}

function ear(side) {
  // side = -1 (left) or 1 (right); mirrored about x = 128. Tips rise above the
  // ruff; bases tuck under the face circle drawn after them.
  const m = (x) => (128 + side * (x - 128)).toFixed(1);
  return `
    <path d="M ${m(50)} 98 Q ${m(42)} 44 ${m(68)} 32 Q ${m(94)} 34 ${m(118)} 66 Z" fill="${C.ginger}" stroke="${C.caramel}" stroke-width="4" stroke-linejoin="round"/>
    <path d="M ${m(62)} 86 Q ${m(58)} 52 ${m(72)} 45 Q ${m(90)} 48 ${m(104)} 68 Z" fill="${C.lightBrown}"/>`;
}

function eye(side) {
  const cx = 128 + side * 34;
  return `
    <g class="veena-eye">
      <ellipse cx="${cx}" cy="128" rx="22" ry="22" fill="${C.ivory}" stroke="${C.darkBrown}" stroke-width="3.5"/>
      <circle cx="${cx}" cy="129" r="17" fill="${C.caramel}"/>
      <circle cx="${cx}" cy="129" r="11" fill="${C.ginger}" opacity="0.6"/>
      <ellipse class="veena-pupil" cx="${cx}" cy="129" rx="7.5" ry="10" fill="${C.espresso}"/>
      <circle cx="${cx - 6}" cy="121" r="4.5" fill="${C.white}"/>
      <circle cx="${cx + 6}" cy="135" r="2" fill="${C.white}" opacity="0.85"/>
    </g>
    <!-- eyelid: hidden unless the blink animation shows it -->
    <path class="veena-lid" opacity="0" d="M ${cx - 24} 128 Q ${cx} 102 ${cx + 24} 128 Q ${cx} 136 ${cx - 24} 128 Z" fill="${C.ginger}" stroke="${C.darkBrown}" stroke-width="3"/>`;
}

/**
 * @param {{ background?: string|null, padding?: number, title?: string }} [opts]
 * @returns {string} standalone SVG markup (viewBox 0 0 256 256)
 */
export function catSvg(opts = {}) {
  const { background = null, padding = 0, title = "VEENA.AI ginger Persian cat" } = opts;
  const s = 256 + padding * 2;
  const bg = background
    ? `<rect x="${-padding}" y="${-padding}" width="${s}" height="${s}" rx="${s * 0.22}" fill="${background}"/>`
    : "";
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${-padding} ${-padding} ${s} ${s}" role="img" aria-label="${title}">
  <title>${title}</title>
  ${bg}
  <g class="veena-head">
    ${ruff(128, 138, 90, 22, 22, C.caramel)}
    ${ruff(128, 138, 86, 22, 22, C.ginger)}
    ${ear(-1)}${ear(1)}
    <circle cx="128" cy="140" r="86" fill="${C.ginger}"/>
    <!-- tabby forehead marks -->
    <path d="M 128 72 L 128 96" stroke="${C.caramel}" stroke-width="6" stroke-linecap="round"/>
    <path d="M 112 76 Q 114 88 118 98" stroke="${C.caramel}" stroke-width="5" stroke-linecap="round" fill="none"/>
    <path d="M 144 76 Q 142 88 138 98" stroke="${C.caramel}" stroke-width="5" stroke-linecap="round" fill="none"/>
    <!-- cream cheeks and muzzle -->
    <ellipse cx="104" cy="170" rx="34" ry="28" fill="${C.cream}"/>
    <ellipse cx="152" cy="170" rx="34" ry="28" fill="${C.cream}"/>
    <ellipse cx="128" cy="186" rx="26" ry="20" fill="${C.cream}"/>
    <!-- cheek tufts -->
    <path d="M 46 160 Q 36 168 44 176 Q 38 184 50 188" stroke="${C.caramel}" stroke-width="4" fill="none" stroke-linecap="round"/>
    <path d="M 210 160 Q 220 168 212 176 Q 218 184 206 188" stroke="${C.caramel}" stroke-width="4" fill="none" stroke-linecap="round"/>
    ${eye(-1)}${eye(1)}
    <!-- nose and mouth: flat Persian face, nose set high -->
    <path d="M 117 156 Q 128 150 139 156 Q 134 166 128 168 Q 122 166 117 156 Z" fill="${C.mediumBrown}" stroke="${C.darkBrown}" stroke-width="2.5" stroke-linejoin="round"/>
    <path class="veena-mouth" d="M 128 168 L 128 176 M 128 176 Q 120 184 112 179 M 128 176 Q 136 184 144 179" stroke="${C.darkBrown}" stroke-width="3" fill="none" stroke-linecap="round"/>
    <!-- whiskers -->
    <g stroke="${C.mediumBrown}" stroke-width="2" stroke-linecap="round" opacity="0.75">
      <path d="M 92 172 L 52 166"/><path d="M 92 178 L 54 180"/><path d="M 94 184 L 60 194"/>
      <path d="M 164 172 L 204 166"/><path d="M 164 178 L 202 180"/><path d="M 162 184 L 196 194"/>
    </g>
  </g>
</svg>`;
}
