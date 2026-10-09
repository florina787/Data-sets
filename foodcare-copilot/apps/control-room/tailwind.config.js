/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: { 950: "#0a1428", 900: "#0f1f3d", 800: "#1a2d52", 700: "#2a4170", 600: "#3d5a8f", 100: "#e3e9f4" },
        cream: { 50: "#fdfbf6", 100: "#faf6ee", 200: "#f2ead9", 300: "#e6dbc2" },
        leaf: { 700: "#1f5c38", 600: "#2f7d4f", 500: "#3f9563", 100: "#e2f1e7" },
        amber: { 700: "#8a5a00", 100: "#fbefd5" },
        brick: { 700: "#9b2c2c", 100: "#f9e1e1" },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
