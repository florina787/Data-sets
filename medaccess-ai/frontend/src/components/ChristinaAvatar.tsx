// Dr. Christina - original SVG illustration of a friendly virtual assistant in a white coat and teal
// blouse. "Dr." is a character name only: Christina is a virtual AI assistant, not a physician.
import type { AvatarState } from "../services/api";

interface Props {
  state: AvatarState;
  size?: number;
  reducedMotion?: boolean;
}

const LABELS: Record<AvatarState, string> = {
  greeting: "waving hello",
  idle: "listening",
  thinking: "thinking",
  speaking: "speaking",
  pointing: "pointing to the results",
  celebrating: "celebrating a successful search",
  explaining: "explaining",
  warning: "highlighting an important safety message",
};

export function ChristinaAvatar({ state, size = 160, reducedMotion = false }: Props) {
  const wave = state === "greeting";
  const point = state === "pointing" || state === "explaining";
  const speaking = state === "speaking" || state === "explaining" || state === "greeting";
  const smileBig = state === "celebrating" || state === "greeting";
  const concerned = state === "warning";
  return (
    <svg
      viewBox="0 0 240 260"
      width={size}
      height={(size * 260) / 240}
      role="img"
      aria-label={`Christina, virtual AI assistant, ${LABELS[state]}`}
      className={`${reducedMotion ? "reduce-motion" : ""} ${state === "celebrating" ? "ch-celebrate" : ""}`}
    >
      <defs>
        <radialGradient id="ch-bg" cx="50%" cy="40%" r="60%">
          <stop offset="0" stopColor="#E0F2F0" />
          <stop offset="1" stopColor="#D0E3F7" />
        </radialGradient>
        <linearGradient id="ch-skin" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#F6D3B8" />
          <stop offset="1" stopColor="#E9B896" />
        </linearGradient>
        <linearGradient id="ch-hair" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#5A3825" />
          <stop offset="1" stopColor="#3B2216" />
        </linearGradient>
        <linearGradient id="ch-coat" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FFFFFF" />
          <stop offset="1" stopColor="#E6EEF5" />
        </linearGradient>
        <linearGradient id="ch-blouse" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#26A69A" />
          <stop offset="1" stopColor="#00796B" />
        </linearGradient>
      </defs>
      <circle cx="120" cy="125" r="112" fill="url(#ch-bg)" />

      <g className="ch-body">
        {/* hair back */}
        <path d="M66 112c-6-52 22-80 54-80s62 26 54 80c-2 24 6 44 10 58H58c4-14 10-34 8-58z" fill="url(#ch-hair)" />
        {/* neck */}
        <path d="M104 140h32v22c0 8-32 8-32 0z" fill="#E2AC88" />
        {/* torso: blouse + coat */}
        <path d="M52 260c0-52 26-86 68-90 42 4 68 38 68 90z" fill="url(#ch-coat)" />
        <path d="M100 168l20 30 20-30c-6-4-14-6-20-6s-14 2-20 6z" fill="url(#ch-blouse)" />
        <path d="M120 198v62" stroke="#C9D6E2" strokeWidth="2" />
        <path d="M100 168l-16 10 20 52 16-32zM140 168l16 10-20 52-16-32z" fill="#F3F7FA" stroke="#D5E0EA" strokeWidth="1.5" />
        {/* stethoscope */}
        <path d="M92 182c-6 22 2 40 18 44" fill="none" stroke="#546E7A" strokeWidth="3" strokeLinecap="round" />
        <circle cx="112" cy="227" r="5" fill="#90A4AE" stroke="#546E7A" strokeWidth="2" />
        {/* ID badge */}
        <g transform="translate(140 206)">
          <rect width="40" height="26" rx="4" fill="#fff" stroke="#1565C0" strokeWidth="1.5" />
          <rect width="40" height="7" rx="3" fill="#1565C0" />
          <text x="20" y="15.5" textAnchor="middle" fontSize="6" fontWeight="700" fill="#17324D">Christina</text>
          <text x="20" y="22.5" textAnchor="middle" fontSize="4.6" fill="#00897B">AI Assistant</text>
        </g>
        {/* left arm (resting) */}
        <path d="M64 196c-10 18-12 40-10 64h22c-2-22 0-40 6-52z" fill="url(#ch-coat)" stroke="#D5E0EA" strokeWidth="1.5" />
        {/* right arm: waves or points */}
        <g className={wave ? "ch-arm-wave" : point ? "ch-arm-point" : ""}>
          <path d="M168 190c14 14 20 40 18 70h-22c2-24-2-42-10-54z" fill="url(#ch-coat)" stroke="#D5E0EA" strokeWidth="1.5" />
          {(wave || point) && <circle cx="176" cy="262" r="9" fill="url(#ch-skin)" />}
        </g>

        {/* head */}
        <ellipse cx="120" cy="102" rx="40" ry="46" fill="url(#ch-skin)" />
        {/* hair front */}
        <path d="M80 98c0-34 18-52 42-52 26 0 40 18 40 44-14-4-34-16-44-30-6 16-20 30-38 38z" fill="url(#ch-hair)" />
        {/* brows */}
        <path d={concerned ? "M96 86l14 4M144 86l-14 4" : "M96 88q7-5 14-1M130 87q7-4 14 1"} stroke="#3B2216" strokeWidth="2.5" fill="none" strokeLinecap="round" />
        {/* eyes */}
        <g className={reducedMotion ? "" : "ch-eyes"}>
          <ellipse cx="104" cy={state === "thinking" ? 98 : 101} rx="4.2" ry="5" fill="#2A1B12" />
          <ellipse cx="136" cy={state === "thinking" ? 98 : 101} rx="4.2" ry="5" fill="#2A1B12" />
          <circle cx="105.5" cy={state === "thinking" ? 96.5 : 99.5} r="1.3" fill="#fff" />
          <circle cx="137.5" cy={state === "thinking" ? 96.5 : 99.5} r="1.3" fill="#fff" />
        </g>
        {/* cheeks */}
        <ellipse cx="96" cy="116" rx="7" ry="4" fill="#F08A80" opacity=".25" />
        <ellipse cx="144" cy="116" rx="7" ry="4" fill="#F08A80" opacity=".25" />
        {/* mouth */}
        {speaking && !reducedMotion ? (
          <ellipse className="ch-mouth-speak" cx="120" cy="127" rx="8" ry="5" fill="#A8433A" />
        ) : concerned ? (
          <path d="M110 129q10-4 20 0" stroke="#A8433A" strokeWidth="3" fill="none" strokeLinecap="round" />
        ) : (
          <path d={smileBig ? "M106 123q14 14 28 0" : "M109 125q11 8 22 0"} stroke="#A8433A" strokeWidth="3" fill={smileBig ? "#fff" : "none"} strokeLinecap="round" />
        )}
        {/* earrings */}
        <circle cx="80" cy="112" r="2.5" fill="#00897B" />
        <circle cx="160" cy="112" r="2.5" fill="#00897B" />
      </g>

      {state === "thinking" && (
        <g fill="#1565C0">
          <circle className="ch-dot" cx="176" cy="54" r="4" />
          <circle className="ch-dot" cx="190" cy="44" r="5" style={{ animationDelay: ".2s" }} />
          <circle className="ch-dot" cx="206" cy="32" r="6" style={{ animationDelay: ".4s" }} />
        </g>
      )}
      {state === "celebrating" && (
        <g fill="#00897B">
          {[[44, 60], [196, 70], [60, 30], [180, 30]].map(([x, y], i) => (
            <path key={i} className="ch-sparkle" style={{ animationDelay: `${i * 0.25}s` }} d={`M${x} ${y - 8}l2 6 6 2-6 2-2 6-2-6-6-2 6-2z`} />
          ))}
        </g>
      )}
      {state === "warning" && (
        <g className="ch-warn" transform="translate(178 30)">
          <circle r="16" fill="#ED6C02" />
          <text y="7" textAnchor="middle" fontSize="22" fontWeight="800" fill="#fff">!</text>
        </g>
      )}
    </svg>
  );
}
