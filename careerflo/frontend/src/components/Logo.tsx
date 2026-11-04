export function Logo({ compact }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
        <rect width="32" height="32" rx="9" fill="#101828" />
        <path d="M8 22h6v-4h5v-4h5" stroke="#fff" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="24" cy="10" r="2.6" fill="#7357FF" />
      </svg>
      {!compact && <span className="whitespace-nowrap text-[15px] font-semibold tracking-tight">Career<span className="text-violet">_flo</span> AI</span>}
    </span>
  );
}
