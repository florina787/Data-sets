/** Original line-art botanical shapes (no stock imagery). Decorative only. */
export function Botanicals({ className = "" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={`pointer-events-none ${className}`} viewBox="0 0 800 800" fill="none">
      <g className="site-leaf" style={{ animationDelay: "-3s" }} stroke="#d7b57a" strokeOpacity=".35" strokeWidth="1.5">
        <path d="M120 640 C 200 480, 320 420, 430 400" /><path d="M200 540 C 160 500, 150 450, 175 410 C 215 445, 225 495, 200 540Z" fill="#d7b57a" fillOpacity=".06" />
        <path d="M290 470 C 260 420, 265 370, 300 335 C 330 380, 325 430, 290 470Z" fill="#d7b57a" fillOpacity=".06" /><path d="M370 425 C 360 375, 380 330, 420 305 C 435 355, 415 400, 370 425Z" fill="#d7b57a" fillOpacity=".06" />
      </g>
      <g className="site-leaf" style={{ animationDelay: "-9s" }} stroke="#a9bba1" strokeOpacity=".28" strokeWidth="1.5">
        <path d="M640 120 C 560 260, 560 380, 610 520" /><ellipse cx="585" cy="230" rx="28" ry="62" transform="rotate(-28 585 230)" fill="#a9bba1" fillOpacity=".07" />
        <ellipse cx="632" cy="330" rx="26" ry="58" transform="rotate(24 632 330)" fill="#a9bba1" fillOpacity=".07" /><ellipse cx="578" cy="430" rx="24" ry="54" transform="rotate(-22 578 430)" fill="#a9bba1" fillOpacity=".07" />
      </g>
      <circle className="site-leaf" cx="690" cy="640" r="90" stroke="#d7b57a" strokeOpacity=".18" style={{ animationDelay: "-5s" }} />
      <circle cx="690" cy="640" r="140" stroke="#d7b57a" strokeOpacity=".08" />
    </svg>
  );
}
