import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

const TONES = {
  violet: { fill: "#7357FF", chip: "bg-violet" }, sky: { fill: "#3B82F6", chip: "bg-blue-500" },
  amber: { fill: "#F59E0B", chip: "bg-amber" }, coral: { fill: "#E5484D", chip: "bg-[#E5484D]" },
  emerald: { fill: "#10B981", chip: "bg-emerald" }, rose: { fill: "#D9727A", chip: "bg-[#D9727A]" },
} as const;
export type Tone = keyof typeof TONES;

/** A multiplayer-style cursor with a name chip: how agents appear while they work. */
export function AgentCursor({ label, tone = "violet", flip, className, delay = 0 }: { label: string; tone?: Tone; flip?: boolean; className?: string; delay?: number }) {
  const t = TONES[tone];
  return (
    <motion.div
      aria-hidden
      className={cn("pointer-events-none absolute z-20 flex items-start gap-0.5", flip && "flex-row-reverse", className)}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: [0, -4, 0], x: [0, 3, 0] }}
      transition={{ opacity: { delay, duration: 0.4 }, y: { delay, duration: 4, repeat: Infinity, ease: "easeInOut" }, x: { delay, duration: 5, repeat: Infinity, ease: "easeInOut" } }}
    >
      <svg width="18" height="18" viewBox="0 0 18 18" className={cn(flip && "-scale-x-100")}>
        <path d="M2 1.5 16 7.2l-6.1 1.9L7.4 15.6Z" fill={t.fill} stroke="white" strokeWidth="1.4" strokeLinejoin="round" />
      </svg>
      <span className={cn("mt-3 rounded-full px-2.5 py-1 text-[11.5px] font-medium text-white shadow-md", t.chip)}>{label}</span>
    </motion.div>
  );
}
