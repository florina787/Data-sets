import flominSvg from "../../public/flomin.svg?raw";

/** Inline FloMin (so the eyelids can blink). Decorative unless a label is given. */
export function FloMinInline({ size = 92, blink = false, wave = false, label }: { size?: number; blink?: boolean; wave?: boolean; label?: string }) {
  const markup = blink ? flominSvg : flominSvg.replace('class="flomin-lids"', 'class="flomin-lids" style="display:none"');
  return (
    <span
      className={`flomin-inline${wave ? " wave" : ""}`}
      style={{ display: "inline-block", width: size, height: size * 1.3 }}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      // Static, bundled SVG asset (not user content).
      dangerouslySetInnerHTML={{ __html: markup }}
    />
  );
}

export function FloMinIcon({ size = 26, alt = "" }: { size?: number; alt?: string }) {
  return <img src="/flomin-icon.svg" width={size} height={size * 1.09} alt={alt} />;
}

export function ChartIcon() {
  return (
    <svg className="ic" viewBox="0 0 30 30" aria-hidden="true">
      <rect x="4" y="15" width="5" height="11" rx="1" fill="#107C41" />
      <rect x="12.5" y="9" width="5" height="17" rx="1" fill="#107C41" />
      <rect x="21" y="4" width="5" height="22" rx="1" fill="#0B4F35" />
    </svg>
  );
}

export function FormulaIcon() {
  return (
    <svg className="ic" viewBox="0 0 30 30" aria-hidden="true">
      <rect x="3" y="3" width="24" height="24" rx="4" fill="#107C41" />
      <rect x="7" y="7" width="16" height="5" rx="1" fill="#E2F0D9" />
      {[0, 1, 2].map((r) => [0, 1, 2].map((c) => <rect key={`${r}${c}`} x={7 + c * 6} y={14 + r * 4} width="4" height="2.6" rx="0.6" fill="#ffffff" />))}
    </svg>
  );
}

export function TrendIcon() {
  return (
    <svg className="ic" viewBox="0 0 30 30" aria-hidden="true">
      <rect x="3" y="3" width="24" height="24" rx="4" fill="#E2F0D9" />
      <polyline points="6,21 12,15 16,18 24,9" fill="none" stroke="#107C41" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="24" cy="9" r="2" fill="#0B4F35" />
    </svg>
  );
}

export function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11.5 20.5 3l-6.8 18-2.6-7.4L3 11.5Z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" /></svg>
  );
}
