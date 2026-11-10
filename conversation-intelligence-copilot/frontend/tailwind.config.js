/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0B1020",
        surface: "#111827",
        elevated: "#17233C",
        line: "rgba(148,163,184,0.14)",
        indigo: { DEFAULT: "#6366F1", soft: "rgba(99,102,241,0.14)" },
        cyan: { DEFAULT: "#22D3EE", soft: "rgba(34,211,238,0.12)" },
        violet: { DEFAULT: "#A78BFA", soft: "rgba(167,139,250,0.14)" },
        ink: "#F8FAFC",
        muted: "#94A3B8",
        faint: "#64748B",
        pos: "#34D399",
        neg: "#F87171",
        neu: "#94A3B8",
        mix: "#FBBF24",
        warn: "#F59E0B",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        card: "0 1px 0 rgba(255,255,255,0.04) inset, 0 10px 30px -12px rgba(2,6,23,0.6)",
        glow: "0 0 0 1px rgba(99,102,241,0.35), 0 12px 40px -12px rgba(99,102,241,0.45)",
      },
      keyframes: { shimmer: { "100%": { transform: "translateX(100%)" } } },
      animation: { shimmer: "shimmer 1.6s infinite" },
    },
  },
  plugins: [],
};
