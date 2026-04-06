describe('Events Page', () => {

  const apiUrl = '/api/events/'

  // 🟢 TC1 – Renginiai su visa informacija (SD-T1)
  it('TC1 - displays events with full information', () => {

    cy.intercept('GET', apiUrl, {
      statusCode: 200,
      body: {
        total: 2,
        events: [
          {
            event_id: 1,
            name: 'Tech Conference',
            date: '2025-05-20',
            time: '18:00',
            place: 'Vilnius',
            price: '10.00',
            categories: ['Tech', 'IT']
          },
          {
            event_id: 2,
            name: 'Music Night',
            date: '2025-05-21',
            time: '19:30',
            place: 'Kaunas',
            price: '5.50',
            categories: ['Music']
          }
        ]
      }
    }).as('getEvents')

    cy.visit('/events')
    cy.wait('@getEvents')

    cy.get('.event-item').should('have.length', 2)

    cy.get('.event-item').eq(0).within(() => {
      cy.contains('h2', 'Tech Conference')
      cy.contains(/^Date:/).parent().invoke('text').should('match', /Date:\s\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}/)
      cy.contains(/^Place:/).parent().should('contain.text', 'Vilnius')
      cy.contains(/^Price:/).parent().should('contain.text', '10,00 €')
      cy.contains(/^Categories:/).parent().should('contain.text', 'Tech, IT')
    })

    cy.get('.event-item').eq(1).within(() => {
      cy.contains('h2', 'Music Night')
      cy.contains(/^Date:/).parent().invoke('text').should('match', /Date:\s\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}/)
      cy.contains(/^Place:/).parent().should('contain.text', 'Kaunas')
      cy.contains(/^Price:/).parent().should('contain.text', '5,50 € ')
      cy.contains(/^Categories:/).parent().should('contain.text', 'Music')
    })

    cy.contains('Total: 2')
  })


  // 🔴 TC2 – Renginys be pavadinimo (SD-T10)
  it('TC2 - hides event without name', () => {

    cy.intercept('GET', apiUrl, {
      statusCode: 200,
      body: {
        total: 1,
        events: [
          {
            event_id: 1,
            name: '',
            date: '2025-05-20',
            time: '18:00',
            place: 'Vilnius',
            price: '10.00',
            categories: ['Tech']
          }
        ]
      }
    }).as('getEvents')

    cy.visit('/events')
    cy.wait('@getEvents')
    cy.get('.event-item').should('have.length', 0)
  })


  // 🔴 TC3 – Renginys be datos (SD-T16)
  it('TC3 - hides event without date', () => {

    cy.intercept('GET', apiUrl, {
      statusCode: 200,
      body: {
        total: 1,
        events: [
          {
            event_id: 1,
            name: 'Test Event',
            date: null,
            time: '18:00',
            place: 'Vilnius',
            price: '10.00',
            categories: ['Tech']
          }
        ]
      }
    }).as('getEvents')

    cy.visit('/events')
    cy.wait('@getEvents')
    cy.get('.event-item').should('have.length', 0)
  })


  // 🟡 TC4 – Renginys be laiko (SD-T14)
  it('TC4 - shows only date when time is missing', () => {

    cy.intercept('GET', apiUrl, {
      statusCode: 200,
      body: {
        total: 1,
        events: [
          {
            event_id: 1,
            name: 'Test Event',
            date: '2025-05-20',
            time: null,
            place: 'Vilnius',
            price: '10.00',
            categories: ['Tech']
          }
        ]
      }
    }).as('getEvents')

    cy.visit('/events')
    cy.wait('@getEvents')
    cy.get('.event-item').should('have.length', 1)
    cy.get('.event-item').first().within(() => {
      cy.contains(/^Date:/).parent().invoke('text').should('match', /^\s*Date:\s\d{4}-\d{2}-\d{2}\s*$/)
    })
  })


  // 🟡 TC5 – Renginys be vietos (SD-T12)
  it('TC5 - shows "-" when place is missing', () => {

    cy.intercept('GET', apiUrl, {
      statusCode: 200,
      body: {
        total: 1,
        events: [
          {
            event_id: 1,
            name: 'Test Event',
            date: '2025-05-20',
            time: '18:00',
            place: null,
            price: '10.00',
            categories: ['Tech']
          }
        ]
      }
    }).as('getEvents')

    cy.visit('/events')
    cy.wait('@getEvents')
    cy.get('.event-item').should('have.length', 1)
    cy.get('.event-item').first().within(() => {
      cy.contains(/^Place:/).parent().invoke('text').should('match', /^\s*Place:\s*-\s*$/)
    })
  })


  // 🟡 TC6 – Renginys be kainos (SD-T13)
  it('TC6 - shows "-" when price is missing', () => {

    cy.intercept('GET', apiUrl, {
      statusCode: 200,
      body: {
        total: 1,
        events: [
          {
            event_id: 1,
            name: 'Test Event',
            date: '2025-05-20',
            time: '18:00',
            place: 'Vilnius',
            price: null,
            categories: ['Tech']
          }
        ]
      }
    }).as('getEvents')

    cy.visit('/events')
    cy.wait('@getEvents')
    cy.get('.event-item').should('have.length', 1)
    cy.get('.event-item').first().within(() => {
      cy.contains(/^Price:/).parent().invoke('text').should('match', /^\s*Price:\s*-\s*$/)
    })
  })


  // 🟡 TC7 – Renginys su nuline kaina (SD-T17)
  it('TC7 - shows 0,00 € when price is 0', () => {

    cy.intercept('GET', apiUrl, {
      statusCode: 200,
      body: {
        total: 1,
        events: [
          {
            event_id: 1,
            name: 'Free Event',
            date: '2025-05-20',
            time: '18:00',
            place: 'Vilnius',
            price: '0.00',
            categories: ['Tech']
          }
        ]
      }
    }).as('getEvents')

    cy.visit('/events')
    cy.wait('@getEvents')
    cy.get('.event-item').should('have.length', 1)
    cy.get('.event-item').first().within(() => {
      cy.contains(/^Price:/).parent().should('contain.text', '0,00 €')
    })
  })


  // 🟡 TC8 – Renginys be kategorijų (SD-T11)
  it('TC8 - shows "-" when categories are missing', () => {

    cy.intercept('GET', apiUrl, {
      statusCode: 200,
      body: {
        total: 1,
        events: [
          {
            event_id: 1,
            name: 'Test Event',
            date: '2025-05-20',
            time: '18:00',
            place: 'Vilnius',
            price: '10.00',
            categories: []
          }
        ]
      }
    }).as('getEvents')

    cy.visit('/events')
    cy.wait('@getEvents')
    cy.get('.event-item').should('have.length', 1)
    cy.get('.event-item').first().within(() => {
      cy.contains(/^Categories:/).parent().invoke('text').should('match', /^\s*Categories:\s*-\s*$/)
    })
  })


  // 🟢 TC9 – Sėkmingai užkrauti renginiai (SD-T27)
  it('TC9 - shows total events count', () => {

    cy.intercept('GET', apiUrl, {
      statusCode: 200,
      body: {
        total: 2,
        events: [
          {
            event_id: 1,
            name: 'Event 1',
            date: '2025-05-20',
            time: '18:00',
            place: 'Vilnius',
            price: '10.00',
            categories: ['Tech']
          },
          {
            event_id: 2,
            name: 'Event 2',
            date: '2025-05-21',
            time: '19:00',
            place: 'Kaunas',
            price: '5.00',
            categories: ['Music']
          }
        ]
      }
    }).as('getEvents')

    cy.visit('/events')
    cy.wait('@getEvents')

    cy.contains('Total: 2')
    cy.get('.event-item').should('have.length', 2)
  })


  // 🔵 TC10 – Renginių užkrovimas (SD-T28)
  it('TC10 - shows loading state', () => {

    cy.intercept('GET', apiUrl, {
      statusCode: 200,
      delay: 1000,
      body: {
        total: 1,
        events: [
          {
            event_id: 1,
            name: 'Delayed Event',
            date: '2025-05-20',
            time: '18:00',
            place: 'Vilnius',
            price: '10.00',
            categories: ['Tech']
          }
        ]
      }
    }).as('getEvents')

    cy.visit('/events')

    cy.contains('Loading events...').should('be.visible')
    cy.wait('@getEvents')
    cy.contains('Loading events...').should('not.exist')
  })


  // 🔴 TC11 – Klaida gaunant renginius (SD-T29)
  it('TC11 - shows error message when API fails', () => {

    cy.intercept('GET', apiUrl, {
      statusCode: 500,
      body: {
        error: 'Failed to load events.'
      }
    }).as('getEvents')

    cy.visit('/events')
    cy.wait('@getEvents')

    cy.contains('Failed to load events.').should('be.visible')
  })


  // 🔴 TC12 – Nėra renginių (SD-T30)
  it('TC12 - shows empty state message', () => {

    cy.intercept('GET', apiUrl, {
      statusCode: 200,
      body: {
        total: 0,
        events: []
      }
    }).as('getEvents')

    cy.visit('/events')
    cy.wait('@getEvents')

    cy.get('.event-item').should('not.exist')
    cy.contains('No events found. Go back to subjects.').should('be.visible')
  })

})
