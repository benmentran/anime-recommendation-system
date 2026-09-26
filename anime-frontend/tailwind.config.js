/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        anilist: {
          bg: '#1d1d1f', card: '#28282b', border: '#3a3a3d', text: '#f5f5f5',
          textMuted: '#9a9a9a', accent: '#00a1d6', accentHover: '#00bfff',
          green: '#2ecc71', blue: '#3498db', yellow: '#f39c12',
          red: '#e74c3c', gray: '#95a5a6',
        },
      },
    },
  },
  plugins: [],
};
