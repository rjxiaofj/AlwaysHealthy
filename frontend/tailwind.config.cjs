/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      borderRadius: {
        card: '24px',
        control: '16px',
      },
      colors: {
        ink: 'var(--color-text-primary)',
        muted: 'var(--color-text-secondary)',
        faint: 'var(--color-text-tertiary)',
        line: 'var(--color-border)',
        canvas: 'var(--color-bg)',
      },
      boxShadow: {
        glass: '0 10px 30px var(--color-shadow)',
      },
    },
  },
  plugins: [],
}
