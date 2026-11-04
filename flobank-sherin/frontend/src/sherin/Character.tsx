import "./character.css";

/**
 * Full-body Sherin: an original, code-rigged SVG character (long black hair, orange-red outfit).
 *
 * DRAFT ASSET: the approved Ghibli portrait is not in the repository yet, so the face here is drawn to the brief
 * (long black hair, soft Ghibli-style features) and must be matched to the portrait and approved before release.
 * Every pose is the same rig, so the identity cannot drift between scenes.
 *
 * Joints: shoulder -> elbow for each arm, hip for each leg, neck for the head. Poses are CSS classes, so animation
 * runs on the compositor and never touches financial or agent logic.
 */
export const POSES = ["idle", "walk", "turn", "point", "think", "work", "success", "warning", "waiting", "error"] as const;
export type Pose = (typeof POSES)[number];
export const CHARACTER_ASSET = { id: "sherin-fullbody-rig", version: "0.1-draft", status: "pending-approval" } as const;

const SKIN = "#F4CDB0", SKIN_SH = "#E7B393", HAIR = "#17110F", HAIR_HI = "#3A2A24", OUT = "#D9472B", OUT_SH = "#B23520", OUT_HI = "#EE6A47", CREAM = "#F7E9D3", SHOE = "#4A2B1E";

function Arm({ side }: { side: "l" | "r" }) {
  const x = side === "l" ? 41 : 79;
  return (
    <g className={`arm arm-${side}`}>
      <path d={`M${x - 5} 84 q5 -4 10 0 l-1 26 q-4 3 -8 0 z`} fill={OUT} stroke={OUT_SH} strokeWidth=".8" />
      <g className={`fore fore-${side}`}>
        <path d={`M${x - 3.5} 108 l7 0 l-.6 22 q-3 2 -5.8 0 z`} fill={SKIN} stroke={SKIN_SH} strokeWidth=".6" />
        <circle cx={x} cy={132} r={4.2} fill={SKIN} stroke={SKIN_SH} strokeWidth=".6" />
        {side === "r" && <path className="finger" d={`M${x} 134 l0 7`} stroke={SKIN_SH} strokeWidth="2.4" strokeLinecap="round" />}
      </g>
    </g>
  );
}

function Leg({ side }: { side: "l" | "r" }) {
  const x = side === "l" ? 53 : 67;
  return (
    <g className={`leg leg-${side}`}>
      <path d={`M${x - 4} 148 l8 0 l-1 40 l-6 0 z`} fill="#3B2A35" />
      <ellipse cx={x + 1.5} cy={192} rx={7} ry={3.6} fill={SHOE} />
    </g>
  );
}

export function SherinCharacter({ pose = "idle", height = 140, facing = 1, title = "Sherin" }: { pose?: Pose; height?: number; facing?: 1 | -1; title?: string }) {
  const w = (height * 120) / 210;
  return (
    <svg viewBox="0 0 120 210" width={w} height={height} role="img" aria-label={`${title} (${pose})`} data-testid="sherin-character"
      data-pose={pose} data-asset={CHARACTER_ASSET.id} data-asset-status={CHARACTER_ASSET.status} className={`sherin-rig pose-${pose}`} style={{ overflow: "visible" }}>
      <ellipse className="shadow" cx="60" cy="196" rx="26" ry="4.5" fill="#062A1F" opacity=".14" />
      <g style={{ transform: facing === -1 ? "scaleX(-1)" : undefined, transformOrigin: "60px 0px", transformBox: "view-box" }}>
        <g className="body-bob">
          {/* hair behind */}
          <path className="hair-back" d="M36 44 q-6 40 -2 92 q12 10 26 6 q14 4 26 -6 q4 -52 -2 -92 z" fill={HAIR} />
          <Leg side="l" />
          <Leg side="r" />
          {/* outfit: orange-red tunic dress with cream collar and sash */}
          <path d="M44 80 q16 -8 32 0 l6 40 q2 16 6 30 q-28 8 -56 0 q4 -14 6 -30 z" fill={OUT} stroke={OUT_SH} strokeWidth=".9" />
          <path d="M50 80 q10 10 20 0 l-3 -3 q-7 6 -14 0 z" fill={CREAM} />
          <path d="M42 116 q18 6 36 0 l1 6 q-19 6 -38 0 z" fill={OUT_SH} />
          <path d="M60 86 l0 28" stroke={OUT_HI} strokeWidth="1" opacity=".7" />
          <path d="M37 148 q23 6 46 0" stroke={OUT_HI} strokeWidth="1.2" fill="none" opacity=".6" />
          <g className="prop prop-tablet"><rect x="49" y="104" width="24" height="17" rx="2" fill="#0B3D2E" /><rect x="51" y="106" width="20" height="13" rx="1" fill="#9BE7C2" opacity=".85" /></g>
          <g className="prop prop-folder"><rect x="47" y="100" width="26" height="20" rx="2" fill={CREAM} stroke="#B8913A" /><path d="M51 106 h16 M51 110 h12 M51 114 h14" stroke="#B8913A" strokeWidth="1.1" /></g>
          <Arm side="l" />
          <Arm side="r" />
          {/* head */}
          <g className="head">
            <rect x="56" y="66" width="8" height="12" fill={SKIN_SH} />
            <ellipse cx="60" cy="47" rx="21" ry="23" fill={SKIN} />
            <ellipse cx="48" cy="57" rx="4" ry="2.2" fill="#F08F86" opacity=".45" />
            <ellipse cx="72" cy="57" rx="4" ry="2.2" fill="#F08F86" opacity=".45" />
            <g className="eyes">
              <ellipse cx="52.5" cy="49" rx="3.3" ry="4.4" fill="#2A1C16" />
              <ellipse cx="68.5" cy="49" rx="3.3" ry="4.4" fill="#2A1C16" />
              <circle cx="53.6" cy="47.4" r="1.2" fill="#fff" />
              <circle cx="69.6" cy="47.4" r="1.2" fill="#fff" />
              <g className="lids"><rect x="48" y="43.5" width="9.5" height="11" fill={SKIN} /><rect x="64" y="43.5" width="9.5" height="11" fill={SKIN} /></g>
            </g>
            <g className="brows" stroke={HAIR} strokeWidth="1.3" strokeLinecap="round" fill="none">
              <path className="brow brow-l" d="M48.5 41.5 q4 -2 8 0" />
              <path className="brow brow-r" d="M64 41.5 q4 -2 8 0" />
            </g>
            <path d="M60.5 53 q.8 2.4 -.8 3" stroke={SKIN_SH} strokeWidth=".9" fill="none" />
            <g className="mouths" fill="none" strokeLinecap="round">
              <path className="m m-smile" d="M55.5 60.5 q4.5 3.6 9 0" stroke="#9C3B2E" strokeWidth="1.4" />
              <path className="m m-open" d="M55 60 q5 6 10 0 z" fill="#9C3B2E" stroke="#9C3B2E" strokeWidth=".8" />
              <path className="m m-flat" d="M56 61.5 h8" stroke="#9C3B2E" strokeWidth="1.3" />
              <path className="m m-o" d="M60 60.2 m-2 0 a2 2.4 0 1 0 4 0 a2 2.4 0 1 0 -4 0" stroke="#9C3B2E" strokeWidth="1.2" />
              <path className="m m-frown" d="M55.5 63 q4.5 -3.4 9 0" stroke="#9C3B2E" strokeWidth="1.4" />
            </g>
            {/* hair front: soft fringe and long side locks */}
            <path d="M38 48 q-2 -28 22 -30 q24 2 22 30 q-4 -12 -12 -16 q-6 8 -20 9 q4 -5 4 -9 q-8 4 -16 16 z" fill={HAIR} />
            <path d="M40 40 q-6 18 -4 46 q3 4 6 2 q-2 -22 2 -40 z" fill={HAIR} />
            <path d="M80 40 q6 18 4 46 q-3 4 -6 2 q2 -22 -2 -40 z" fill={HAIR} />
            <path d="M50 22 q8 -4 16 0" stroke={HAIR_HI} strokeWidth="1.4" fill="none" opacity=".8" />
            <circle cx="74" cy="31" r="2.6" fill={OUT} stroke={OUT_SH} strokeWidth=".6" />
          </g>
        </g>
      </g>
      {/* state badges sit outside the flip so text stays readable */}
      <g className="badge badge-success"><path d="M20 24 l3 -7 l3 7 l7 3 l-7 3 l-3 7 l-3 -7 l-7 -3 z" fill="#B8913A" /><path d="M98 14 l2 -4 l2 4 l4 2 l-4 2 l-2 4 l-2 -4 l-4 -2 z" fill="#2BB673" /></g>
      <g className="badge badge-warning"><circle cx="96" cy="18" r="10" fill="#A86A12" /><path d="M96 11 v9 M96 24 v.5" stroke="#fff" strokeWidth="3" strokeLinecap="round" /></g>
      <g className="badge badge-error"><circle cx="96" cy="18" r="10" fill="#B4413C" /><path d="M91.5 13.5 l9 9 M100.5 13.5 l-9 9" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" /></g>
      <g className="badge badge-waiting"><circle cx="96" cy="18" r="10" fill="#0F5C43" /><path d="M91.5 11 h9 l-4.5 7 l4.5 7 h-9 l4.5 -7 z" fill="none" stroke="#fff" strokeWidth="1.6" strokeLinejoin="round" /></g>
      <g className="badge badge-think"><circle cx="88" cy="22" r="3" fill="#fff" stroke="#BFE3D2" /><circle cx="96" cy="13" r="5" fill="#fff" stroke="#BFE3D2" /><text x="96" y="15.5" fontSize="7" textAnchor="middle" fill="#0F5C43">…</text></g>
    </svg>
  );
}
