import { useMemo } from "react";
import { catSvg } from "../brand/catSvg.mjs";
import { cn } from "./ui";

export type CatMood = "idle" | "listening" | "thinking" | "still";

/** The VEENA mascot. Rendered from the same SVG source as the app icon. */
export function CatMark({ size = 40, mood = "still", className, label }: { size?: number; mood?: CatMood; className?: string; label?: string }) {
  const svg = useMemo(() => catSvg({ title: label ?? "VEENA.AI" }), [label]);
  return (
    <span
      className={cn("veena-cat inline-block shrink-0", mood !== "still" && `is-${mood}`, className)}
      style={{ width: size, height: size }}
      // Static, generated SVG from our own module, never user input.
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

export function Wordmark({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const cls = { sm: "text-lg", md: "text-xl", lg: "text-4xl" }[size];
  return (
    <span className={cn("font-semibold tracking-tight text-bark", cls)}>
      veena<span className="text-ginger">.ai</span>
    </span>
  );
}
