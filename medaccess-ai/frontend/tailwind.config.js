/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: "#1565C0", 50: "#E8F1FB", 100: "#D0E3F7", 600: "#1565C0", 700: "#0F4C92", 800: "#0B3A70" },
        teal: { DEFAULT: "#00897B", 50: "#E0F2F0", 100: "#B2DFDB", 600: "#00897B", 700: "#00695C" },
        canvas: "#F5F9FC",
        ink: "#17324D",
        ok: "#2E7D32",
        warn: "#ED6C02",
        danger: "#D32F2F",
      },
      fontFamily: { sans: ["Inter", "Segoe UI", "system-ui", "-apple-system", "sans-serif"] },
      boxShadow: { card: "0 1px 2px rgba(23,50,77,.06), 0 4px 16px rgba(23,50,77,.06)" },
    },
  },
  plugins: [],
};
