/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        darkbg: "#0f172a",
        severityNormal: "#22c55e",
        severityWarning: "#eab308",
        severityCritical: "#ef4444",
      },
    },
  },
  plugins: [],
}
