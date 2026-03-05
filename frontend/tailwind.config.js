/** @type {import('tailwindcss').Config} */
module.exports = {
    content: ['./app/**/*.{js,ts,jsx,tsx}', './components/**/*.{js,ts,jsx,tsx}'],
    theme: {
        extend: {
            colors: {
                bg: '#0d0f14',
                surface: '#141720',
                card: '#1a1e2e',
                border: '#252a3a',
                accent: '#3b82f6',
                green: '#22c55e',
                red: '#ef4444',
                muted: '#6b7280',
                text: '#e2e8f0',
            },
            fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
        },
    },
    plugins: [],
}
