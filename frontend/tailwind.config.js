/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // deep institutional dark
        base: "#05070D",
        bg: "#070A12",
        bg2: "#0B1020",
        surface: "#101522",
        surface2: "#141A2A",
        line: "rgba(255,255,255,0.08)",
        line2: "rgba(255,255,255,0.14)",
        muted: "#8693ab",
        faint: "#5b6680",
        text: "#e9eef7",
        accent: "#35e0f0",      // electric cyan
        accent2: "#7c6cff",     // violet
        profit: "#27d18b",
        warn: "#f6b73c",
        danger: "#ff5d6c",
        shadowc: "#9c8cff",     // shadow / non-actionable
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(53,224,240,0.25), 0 0 24px -6px rgba(53,224,240,0.35)",
        card: "0 1px 0 rgba(255,255,255,0.04) inset, 0 18px 40px -24px rgba(0,0,0,0.8)",
      },
      keyframes: {
        pulseDot: { "0%,100%": { opacity: "1" }, "50%": { opacity: "0.35" } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
        rise: { "0%": { opacity: "0", transform: "translateY(6px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
      },
      animation: {
        pulseDot: "pulseDot 1.8s ease-in-out infinite",
        shimmer: "shimmer 1.4s infinite",
        rise: "rise .25s ease-out both",
      },
    },
  },
  plugins: [],
};
