describe('Events Page Filter Tests', () => {
  const apiUrl = '/api/events/'
  const filterRoute = { method: 'GET', pathname: '/api/events/filter/' }

  const allEvents = [
    {
      event_id: 1,
      name: 'Vilnius Cheap Event',
      date: '2026-03-15',
      time: '18:00',
      place: 'Vilnius',
      price: '5.00',
      categories: ['Tech']
    },
    {
      event_id: 2,
      name: 'Vilnius Mid Event',
      date: '2026-03-20',
      time: '19:00',
      place: 'Vilnius',
      price: '50.00',
      categories: ['Music']
    },
    {
      event_id: 3,
      name: 'Kaunas Mid Event',
      date: '2026-03-25',
      time: '20:00',
      place: 'Kaunas',
      price: '20.00',
      categories: ['Art']
    },
    {
      event_id: 4,
      name: 'Klaipėda Expensive Event',
      date: '2026-04-05',
      time: '18:00',
      place: 'Klaipėda',
      price: '150.00',
      categories: ['Business']
    },
    {
      event_id: 5,
      name: 'Vilnius Outside Date Event',
      date: '2026-04-15',
      time: '18:00',
      place: 'Vilnius',
      price: '20.00',
      categories: ['Tech']
    },
  ]

  const visitEventsPage = () => {
    cy.intercept('GET', apiUrl, {
      statusCode: 200,
      body: { total: allEvents.length, events: allEvents }
    }).as('getEvents')

    cy.visit('/events')
    cy.wait('@getEvents')
  }

  it('filters by price range 10-100', () => {
    visitEventsPage()

    cy.intercept(filterRoute, {
      statusCode: 200,
      body: {
        total: 2,
        events: [allEvents[1], allEvents[2]]
      }
    }).as('getFilteredEvents')

    cy.get('#maxPrice').clear().type('10')
    cy.get('#minPrice').clear().type('100')
    cy.wait('@getFilteredEvents')

    cy.get('.event-item').should('have.length', 2)
    cy.contains('Vilnius Mid Event').should('be.visible')
    cy.contains('Kaunas Mid Event').should('be.visible')
  })

  it('filters by city Vilnius', () => {
    visitEventsPage()

    cy.intercept(filterRoute, {
      statusCode: 200,
      body: {
        total: 3,
        events: [allEvents[0], allEvents[1], allEvents[4]]
      }
    }).as('getFilteredEvents')

    cy.get('#city').select('Vilnius')
    cy.wait('@getFilteredEvents')

    cy.get('.event-item').should('have.length', 3)
    cy.get('.event-item h2')
      .then(($items) => [...$items].map((el) => el.innerText.trim()))
      .should('deep.equal', [
        'Vilnius Cheap Event',
        'Vilnius Mid Event',
        'Vilnius Outside Date Event'
      ])
  })

  it('filters by date range 2026-03-10 to 2026-04-10', () => {
    visitEventsPage()

    cy.intercept(filterRoute, {
      statusCode: 200,
      body: {
        total: 4,
        events: [allEvents[0], allEvents[1], allEvents[2], allEvents[3]]
      }
    }).as('getFilteredEvents')

    cy.get('#startDate').clear().type('2026-03-10')
    cy.get('#endDate').clear().type('2026-04-10')
    cy.wait('@getFilteredEvents')

    cy.get('.event-item').should('have.length', 4)
    cy.contains('Vilnius Cheap Event').should('be.visible')
    cy.contains('Klaipėda Expensive Event').should('be.visible')
  })

  it('filters by min_price 0, max_price 10 and city Vilnius', () => {
    visitEventsPage()

    cy.intercept(filterRoute, {
      statusCode: 200,
      body: {
        total: 1,
        events: [allEvents[0]]
      }
    }).as('getFilteredEvents')

    cy.get('#city').select('Vilnius')
    cy.get('#minPrice').clear().type('0')
    cy.get('#maxPrice').clear().type('10')
    cy.wait('@getFilteredEvents')

    cy.get('.event-item').should('have.length', 1)
    cy.contains('Vilnius Cheap Event').should('be.visible')
  })

  it('clears filters and returns all events', () => {
    visitEventsPage()

    cy.intercept(filterRoute, {
      statusCode: 200,
      body: { total: allEvents.length, events: allEvents }
    }).as('getFiltered')

    cy.get('#city').select('Vilnius')
    cy.get('#minPrice').clear().type('10')
    cy.get('#maxPrice').clear().type('100')
    cy.wait('@getFiltered')

    cy.intercept('GET', apiUrl, {
      statusCode: 200,
      body: { total: allEvents.length, events: allEvents }
    }).as('getAllEvents')

    cy.get('button.secondary').click()
    cy.wait('@getAllEvents')
    cy.wait(500) // Allow DOM update

    cy.get('#city').should('have.value', '')
    cy.get('#minPrice').should('have.value', '')
    cy.get('#maxPrice').should('have.value', '')
    cy.get('.event-item').should('have.length', allEvents.length)
  })

  it('shows error and clears filters when min_price > max_price', () => {
    visitEventsPage()

    cy.get('#minPrice').clear().type('100').blur()
    cy.get('#maxPrice').clear().type('10').blur()
    cy.wait(100)

    cy.get('.error-message')
      .should('be.visible')
      .and('contain.text', 'Klaida: maksimali kaina negali būti mažesnė už minimalią.')

    cy.get('#minPrice').should('have.value', '100')
    cy.get('#maxPrice').should('have.value', '10')
    cy.get('.event-item').should('have.length', 0)
  })

  it('shows error and clears filters when start_date > end_date', () => {
    visitEventsPage()

    cy.get('#startDate').clear().type('2026-04-20').blur()
    cy.get('#endDate').clear().type('2026-04-01').blur()
    cy.wait(100)

    cy.get('.error-message')
      .should('be.visible')
      .and('contain.text', 'Klaida: pabaigos data negali būti ankstesnė už pradžios datą.')

    cy.get('#startDate').should('have.value', '2026-04-20')
    cy.get('#endDate').should('have.value', '2026-04-01')
    cy.get('.event-item').should('have.length', 0)
  })
})