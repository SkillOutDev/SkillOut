describe('URL to Study Subjects Flow', () => {
  const scrapeUrl = '/api/scrape-text/'
  const latestSubjectsUrl = '/api/get-latest-subjects/'
  const studentSubjectsUrl = '/api/student/1/subjects/'

  it('SD-T90 - shows URL form page with URL field and Submit button', () => {
    cy.visit('/')

    cy.get('#urlInput').should('be.visible').and('have.attr', 'type', 'url')
    cy.contains('button', 'Submit').should('be.visible')
  })

  it('SD-T91 - shows backend URL format validation message for invalid scheme', () => {
    cy.intercept('POST', scrapeUrl, {
      statusCode: 400,
      body: { error: 'URL must start with http:// or https://.' },
    }).as('scrapeInvalidUrl')

    cy.visit('/')
    cy.get('#urlInput').type('ftp://example.com/program')
    cy.contains('button', 'Submit').click()

    cy.wait('@scrapeInvalidUrl')
    cy.contains('URL must start with http:// or https://.').should('be.visible')
  })

  it('SD-T92 - shows "Submitting..." during scrape and redirects to subjects with separate list items', () => {
    cy.intercept('POST', scrapeUrl, {
      statusCode: 200,
      delay: 700,
      body: {
        message: 'Scrape and AI extraction completed successfully.',
        study_subjects: ['Programavimas', 'Duomenu bazes'],
        subjects_count: 2,
      },
    }).as('scrapeSuccess')

    cy.intercept('GET', latestSubjectsUrl, {
      statusCode: 200,
      body: {
        study_subjects: ['Programavimas', 'Duomenu bazes'],
      },
    }).as('latestSubjects')

    cy.intercept('GET', studentSubjectsUrl, {
      statusCode: 200,
      body: {
        subjects: [],
      },
    }).as('studentSubjects')

    cy.visit('/')
    cy.get('#urlInput').type('https://example.com/program')
    cy.contains('button', 'Submit').click()

    cy.contains('button', 'Submitting...').should('be.visible')

    cy.wait('@scrapeSuccess')
    cy.wait('@latestSubjects')
    cy.wait('@studentSubjects')

    cy.location('pathname').should('eq', '/subjects')

    cy.get('.subjects-list .subject-item').should('have.length', 2)
    cy.contains('.subject-item', 'Programavimas').should('be.visible')
    cy.contains('.subject-item', 'Duomenu bazes').should('be.visible')

    cy.get('.subjects-list .subject-item').each(($item) => {
      expect($item.text().trim()).to.not.equal('')
    })
  })

  it('SD-T93 - shows empty list message when no subjects are found', () => {
    cy.intercept('GET', latestSubjectsUrl, {
      statusCode: 200,
      body: {
        study_subjects: [],
      },
    }).as('latestSubjectsEmpty')

    cy.intercept('GET', studentSubjectsUrl, {
      statusCode: 200,
      body: {
        subjects: [],
      },
    }).as('studentSubjects')

    cy.visit('/subjects')
    cy.wait('@latestSubjectsEmpty')
    cy.wait('@studentSubjects')

    cy.contains('List is empty! Add subjects below or Go Back to try and detect subjects again.').should('be.visible')
  })

  ;[
    'HTTP error: 404',
    'Failed after 3 attempts: Request timed out',
    'Request failed: network issue',
    'Ollama request failed: model offline',
  ].forEach((errorMessage) => {
    it(`SD-T94 - shows scrape failure message: ${errorMessage}`, () => {
      cy.intercept('POST', scrapeUrl, {
        statusCode: errorMessage.startsWith('Ollama') ? 500 : 400,
        body: { error: errorMessage },
      }).as('scrapeFailure')

      cy.visit('/')
      cy.get('#urlInput').type('https://example.com/program')
      cy.contains('button', 'Submit').click()

      cy.wait('@scrapeFailure')
      cy.contains(errorMessage).should('be.visible')
    })
  })
})
