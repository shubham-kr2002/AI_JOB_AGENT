/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Custom hacker/terminal theme
        terminal: {
          bg: '#0f172a',      // slate-900
          surface: '#1e293b', // slate-800
          border: '#334155',  // slate-700
          text: '#e2e8f0',    // slate-200
          muted: '#94a3b8',   // slate-400
        },
        accent: {
          primary: '#10b981',   // emerald-500
          secondary: '#34d399', // emerald-400
          glow: '#059669',      // emerald-600
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'scan': 'scan 1.5s ease-in-out infinite',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px #10b981, 0 0 10px #10b981' },
          '100%': { boxShadow: '0 0 10px #10b981, 0 0 20px #10b981, 0 0 30px #10b981' },
        },
        scan: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        }
      },
    },
  },
  plugins: [],
}
