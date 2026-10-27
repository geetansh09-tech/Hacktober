/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#06080c", 900: "#0a0d13", 850: "#0e121a", 800: "#131823", 700: "#1b2230", 600: "#263044" },
        signal: { DEFAULT: "#22d3ee", dim: "#0e7490" },
        infer: { DEFAULT: "#fbbf24", dim: "#92400e" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: { glow: "0 0 0 1px rgba(34,211,238,.35), 0 0 24px -4px rgba(34,211,238,.35)" },
    },
  },
  plugins: [],
};
