/** @type {import('tailwindcss').Config} */
// Flo & Jerry navy design system. Existing class names keep their roles: "navy" text is
// ink (light on the dark theme), "cream" backgrounds are page surfaces, "bg-white" is a card.
const text = {
  navy: { 950: "#ffffff", 900: "#f8fafc", 800: "#e2e8f0", 700: "#cbd5e1", 600: "#94a3b8", 100: "#0b1b30" },
  cream: { 50: "#f8fafc", 100: "#e2e8f0", 200: "#94a3b8", 300: "#cbd5e1" },
  leaf: { 700: "#34d399", 600: "#10b981", 500: "#10b981", 100: "#6ee7b7" },
  amber: { 700: "#fbbf24", 100: "#fde68a" },
  brick: { 700: "#f87171", 100: "#fca5a5" },
};
const bg = {
  navy: { 950: "#050e1c", 900: "#091a30", 800: "#152e4c", 700: "#1e3a5f", 600: "#2563eb", 100: "#17345a" },
  cream: { 50: "#071426", 100: "#0c1e35", 200: "#152e4c", 300: "#233b58" },
  white: "#10243d",
  leaf: { 700: "#047857", 600: "#059669", 500: "#10b981", 100: "#0f3b3a" },
  amber: { 700: "#b45309", 100: "#3a3220" },
  brick: { 700: "#b91c1c", 100: "#3d2230" },
};
const border = {
  navy: { 700: "#233b58", 600: "#2e4d74", 100: "#233b58" },
  cream: { 200: "#1a3150", 300: "#233b58" },
};
const brand = {
  royal: { 700: "#1d4ed8", 600: "#2563eb", 500: "#3b82f6", 400: "#60a5fa" },
  ice: { 400: "#38bdf8", 300: "#7dd3fc" },
  gold: { 500: "#d9a441", 400: "#e9b95b", 300: "#f3d18a" },
  surface: { base: "#071426", side: "#091a30", card: "#10243d", raised: "#152e4c", line: "#233b58" },
};

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: brand,
      textColor: { ...text, ...brand },
      backgroundColor: { ...bg, ...brand },
      borderColor: { ...border, ...brand },
      ringColor: { navy: { 600: "#3b82f6" }, ...brand },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        card: "0 1px 0 rgba(255,255,255,0.03) inset, 0 8px 24px -12px rgba(0,0,0,0.6)",
        glow: "0 0 0 1px rgba(56,189,248,0.25), 0 8px 30px -10px rgba(37,99,235,0.45)",
      },
    },
  },
  plugins: [],
};
