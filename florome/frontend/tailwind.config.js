/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#F6F6FC",
        ink: { DEFAULT: "#0E1024", soft: "#4A4E6E", mute: "#8A8DAA" },
        dome: { 50: "#EEF0FF", 100: "#E0E3FF", 200: "#C7CCFF", 300: "#A3AAFB", 400: "#7C84F2", 500: "#5B63E6", 600: "#4A4FD1", 700: "#3B3DAA", 900: "#14164A" },
        night: { DEFAULT: "#080A1A", 800: "#0D1030", 700: "#141846" },
        ember: "#F26B2E",
        ok: "#1F9D6B",
        warn: "#D9921A",
        bad: "#E0534A",
      },
      fontFamily: {
        sans: ['"Inter"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
        display: ['"Archivo"', '"Inter"', "ui-sans-serif", "sans-serif"],
      },
      boxShadow: { tile: "0 1px 0 rgba(255,255,255,.9) inset, 0 18px 40px -18px rgba(59,61,170,.35)" },
    },
  },
  plugins: [],
};
