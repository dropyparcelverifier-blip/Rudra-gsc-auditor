/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
      colors: {
        brand: { 50: '#fef3e2', 100: '#fde4b9', 500: '#f97316', 600: '#ea580c', 700: '#c2410c' },
      },
    },
  },
  plugins: [],
}
