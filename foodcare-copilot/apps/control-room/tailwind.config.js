/** @type {import('tailwindcss').Config} */
// Flo & Jerry navy design system. Existing class names keep their roles: "navy" text is
// ink (light on the dark theme), "cream" backgrounds are page surfaces, "bg-white" is a card.
const text = {
  // Flo & Jerry 3.0: ivory ink on midnight navy. "navy" text keeps its role (ink), now warmer.
  navy: { 950: "#ffffff", 900: "#F3F0E9", 800: "#E6E1D6", 700: "#CBC6BA", 600: "#A3AEBC", 100: "#091321" },
  cream: { 50: "#F3F0E9", 100: "#E6E1D6", 200: "#A3AEBC", 300: "#CBC6BA" },
  leaf: { 700: "#5FD3A5", 600: "#3FBF8C", 500: "#3FBF8C", 100: "#8FE3C2" },
  amber: { 700: "#E8B04E", 100: "#F2D59A" },
  brick: { 700: "#F08A8A", 100: "#F6B8B8" },
};
const bg = {
  navy: { 950: "#060D18", 900: "#091321", 800: "#17283C", 700: "#1F3550", 600: "#45C5B8", 100: "#1A2E45" },
  cream: { 50: "#091321", 100: "#0F1D2F", 200: "#17283C", 300: "#22374F" },
  white: "#122238",
  leaf: { 700: "#1F7A5C", 600: "#2A9470", 500: "#3FBF8C", 100: "#123A33" },
  amber: { 700: "#9A6B1A", 100: "#3A3020" },
  brick: { 700: "#B33A3A", 100: "#3D2230" },
};
const border = {
  navy: { 700: "#2A3F57", 600: "#3A5573", 100: "#2A3F57" },
  cream: { 200: "#1E3249", 300: "#2A3F57" },
};
const brand = {
  // "royal" and "ice" are now Refined Teal (selection, focus, links); "gold" is Champagne Gold (primary action).
  royal: { 700: "#2C9C91", 600: "#34B0A4", 500: "#45C5B8", 400: "#6FD6CB" },
  ice: { 400: "#45C5B8", 300: "#86DED5" },
  gold: { 500: "#D7B77A", 400: "#E0C48F", 300: "#ECDBB5" },
  surface: { base: "#091321", side: "#0C1828", card: "#122238", raised: "#17283C", line: "#2A3F57" },
  // Semantic names for new code (FLO_JERRY_3_DESIGN_SYSTEM.md)
  midnight: { DEFAULT: "#091321", 900: "#060D18" },
  elevated: { DEFAULT: "#17283C", 2: "#1F3550" },
  champagne: { DEFAULT: "#D7B77A", soft: "#ECDBB5", deep: "#B8955A" },
  teal: { DEFAULT: "#45C5B8", soft: "#86DED5", deep: "#2C9C91" },
  ink: { DEFAULT: "#F3F0E9", muted: "#A3AEBC", faint: "#7D8A9B" },
  risk: { DEFAULT: "#E26D6D", amber: "#E8B04E" },
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
        card: "0 1px 0 rgba(255,255,255,0.035) inset, 0 10px 30px -14px rgba(0,0,0,0.65)",
        glow: "0 0 0 1px rgba(69,197,184,0.30), 0 8px 30px -12px rgba(69,197,184,0.40)",
        gold: "0 0 0 1px rgba(215,183,122,0.35), 0 10px 32px -14px rgba(215,183,122,0.45)",
      },
    },
  },
  plugins: [],
};
