const { defineConfig } = require('cypress')

module.exports = defineConfig({
  e2e: {
    specPattern: 'cypress/e2e/**/*.cy.js',
    baseUrl: 'http://127.0.0.1:5173',
    supportFile: false,
    setupNodeEvents(on, config) {
      return config
    },
  },
})