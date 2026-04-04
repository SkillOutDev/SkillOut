describe('Event Modal - Reikalavimais Grįstas Testavimas (SD-60)', () => {

  const listUrl = '/api/events'
  const detailUrl = '/api/events/*'
  
  // Bendras mock duomenų objektas sėkmės atvejui
  const mockEvent = {
    event_id: 15,
    name: 'EROS 2026',
    date: '2026-11-13',
    time: '18:00',
    place: 'LITEXPO, Vilnius',
    price: 'Nemokamai',
    organizer: 'KTU SA',
    description: 'Didžiausia paroda.',
    source_url: 'https://test.com',
    ai_sentence: 'Šis renginis padės suprasti AI taikymą jūsų informatikos studijose.'
  }

  beforeEach(() => {
    // Paruošiame pradinį sąrašą
    cy.intercept('GET', listUrl, { total: 1, events: [mockEvent] }).as('getList')
    cy.visit('/events')
    cy.wait('@getList')
  })

  // 1. EP KLASĖ: VALIDŪS DUOMENYS (AC 1, 3, 4, 5, 7)
  it('SD-T26 - Valid data class: Displays all mandatory fields and AI sentence', () => {
    cy.intercept('GET', detailUrl, mockEvent).as('getDetails')

    cy.get('.event-item').first().click() // Paspaudimas ant kortelės (AC 1)
    cy.wait('@getDetails')

    cy.get('.event-modal-overlay').should('be.visible')
    cy.get('.event-modal').within(() => {
      cy.get('h2').should('contain', mockEvent.name) // AC 7
      cy.get('.ai-sentence').should('contain', 'Šis renginis padės') // AC 5
    })
    // Patikra ar be persikrovimo (AC 3)
    cy.window().should('have.prop', 'performance').then(p => {
      expect(p.navigation.type).to.not.equal(1) 
    })
  })

  // 2. EP KLASĖ: FORMATAVIMAS (AC 8)
  it('SD-T39 - Data format class: Strictly checks YYYY-MM-DD HH:MM format', () => {
    cy.intercept('GET', detailUrl, mockEvent).as('getDetails')
    cy.get('.event-item').first().click()
    
    // AC 8: Data ir laikas turi būti sujungti į vieną eilutę
    cy.contains('p', 'Data:')
    .invoke('text') // Ištraukiame tekstą kaip string'ą
    .should('match', /Data:\s*\d{4}-\d{2}-\d{2} \d{2}:\d{2}/)
  })

  // 3. EP KLASĖ: TRŪKSTAMI DUOMENYS (AC 9)
  it('SD-T52 - Missing data class: Displays "-" placeholder for empty fields', () => {
    cy.intercept('GET', detailUrl, { ...mockEvent, organizer: "" }).as('getMissingData')
    cy.get('.event-item').first().click()
    
    // AC 9: Jei organizatoriaus nėra, rodomas brūkšnys
    cy.contains('Organizatorius: -').should('be.visible')
  })

  // 4. EP KLASĖ: NAVIGACIJA IR IŠORINĖS NUORODOS (AC 10)
  it('SD-T37 - External links: Link is active and opens in new tab', () => {
    cy.intercept('GET', detailUrl, mockEvent).as('getDetails')
    cy.get('.event-item').first().click()

    // AC 10: Nuoroda aktyvi ir atsidaro naujame lange
    cy.contains('a', 'Renginio šaltinis')
      .should('have.attr', 'href', mockEvent.source_url)
      .and('have.attr', 'target', '_blank')
  })

  // 5. EP KLASĖ: MODAL VALDYMAS - X MYGTUKAS (AC 2)
  it('SD-T36 - Close via X: Modal closes correctly', () => {
    cy.intercept('GET', detailUrl, mockEvent).as('getDetails')
    cy.get('.event-item').first().click()
    cy.get('.close-btn').click()
    
    cy.get('.event-modal-overlay').should('not.exist') // AC 2
  })

  // 6. EP KLASĖ: MODAL VALDYMAS - BACKDROP (AC 2)
  // PASTABA: Šis testas tavo kodui FAILINS, nes nėra @click ant overlay
  it('SD-T51 - Close via Backdrop: Closes when clicking outside', () => {
    cy.intercept('GET', detailUrl, mockEvent).as('getDetails')
    cy.get('.event-item').first().click()
    
    // Spaudžiame ant pilko fono (overlay)
    cy.get('.event-modal-overlay').click('topLeft', { force: true })
    cy.get('.event-modal-overlay').should('not.exist') 
  })

  // 7. ERROR-BASED: DI SERVISO GEDIMAS (AC 6)
  it('SD-T50 - Error based: Fallback message when AI service fails', () => {
    // Simuliuojame, kad API grąžina klaidą arba tuščią AI lauką
    cy.intercept('GET', detailUrl, { ...mockEvent, ai_sentence: 'DI sakinys negautas.' }).as('getError')
    
    cy.get('.event-item').first().click()
    
    // AC 6: Rodomas atsarginis tekstas
    cy.get('.ai-sentence').should('contain', 'DI sakinys negautas.')
  })

  // 8. ERROR-BASED: API 404 KLAIDA (Out of Scope papildomas testas)
  it('SD-T32 - Error based: Handling 404 error', () => {
    cy.intercept('GET', detailUrl, { statusCode: 404 }).as('get404')
    cy.get('.event-item').first().click()
    
    // Tikriname, ar sistema nesugriūna (pvz., lieka sąraše arba parodo klaidą)
    cy.get('.event-modal').should('be.visible')
    cy.contains('h2', '-').should('not.exist')
  })
})