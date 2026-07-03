/** Trench Design tokens -- Margin IQ brand system.
 * Dark-first, high-contrast, command-center feel. Numbers are the hero. */
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        obsidian: "#0D0D0D",
        surface: "#161616",
        "surface-raised": "#1D1D1D",
        "surface-hover": "#202020",
        outline: "#2A2A2A",
        fire: "#EC5B13",
        "fire-dim": "rgba(236, 91, 19, 0.15)",
        "on-surface": "#F8DDD4",
        "on-surface-variant": "#B8A79E",
        star: "#4ADE80",
        plowhorse: "#60A5FA",
        puzzle: "#FACC15",
        dog: "#F87171",
        error: "#FF6B6B",
      },
      borderRadius: {
        none: "0px",
        DEFAULT: "0px",
        full: "9999px",
      },
      fontFamily: {
        display: ["'Bebas Neue'", "sans-serif"],
        body: ["'DM Sans'", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
      boxShadow: {
        glow: "0 0 15px rgba(236, 91, 19, 0.35)",
      },
    },
  },
  plugins: [],
};
