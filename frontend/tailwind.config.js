/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ["'IBM Plex Mono'", "monospace"],
        sans: ["'IBM Plex Sans'", "sans-serif"],
        display: ["'Russo One'", "sans-serif"],
      },
      colors: {
        space: {
          950: "#03050d",
          900: "#070c1a",
          800: "#0d1530",
          700: "#121d42",
          600: "#1a2754",
        },
        asteroid: {
          DEFAULT: "#f97316",
          dim: "#7c3212",
          glow: "#fb923c",
        },
        star: {
          DEFAULT: "#e2e8f0",
          dim: "#64748b",
          muted: "#94a3b8",
        },
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.3s ease-out",
        orbit: "orbit 20s linear infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        orbit: {
          "0%": { transform: "rotate(0deg) translateX(120px) rotate(0deg)" },
          "100%": { transform: "rotate(360deg) translateX(120px) rotate(-360deg)" },
        },
      },
      backgroundImage: {
        "star-field":
          "radial-gradient(ellipse at 20% 50%, #1a2754 0%, #03050d 70%)",
      },
    },
  },
  plugins: [],
};
