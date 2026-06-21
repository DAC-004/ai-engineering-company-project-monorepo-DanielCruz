const plugin = require('tailwindcss/plugin');

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './application.html'],
  theme: {
    extend: {
      colors: {
        hcBlue: '#0E3A5D',
        hcTeal: '#0E7490',
        hcMint: '#DFF7F2',
        hcInk: '#0F172A'
      },
      maxWidth: {
        hc: '90rem',
        'hc-form': '52rem'
      }
    }
  },
  plugins: [
    plugin(function ({ addComponents, theme }) {
      addComponents({
        '.hc-container': {
          width: '100%',
          maxWidth: theme('maxWidth.hc'),
          marginLeft: 'auto',
          marginRight: 'auto',
          paddingLeft: 'clamp(1.25rem, 4vw, 4rem)',
          paddingRight: 'clamp(1.25rem, 4vw, 4rem)'
        },
        '.hc-form-shell': {
          width: '100%',
          maxWidth: theme('maxWidth.hc-form'),
          marginLeft: 'auto',
          marginRight: 'auto',
          paddingLeft: 'clamp(1.25rem, 4vw, 4rem)',
          paddingRight: 'clamp(1.25rem, 4vw, 4rem)'
        }
      });
    })
  ]
};
