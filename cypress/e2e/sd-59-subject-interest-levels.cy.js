describe('SD-59 - Subject Interest Levels', () => {

  const PAGE_URL = 'http://localhost:8888/cypress/fixtures/subject-interest-page.html'

  beforeEach(() => {
    cy.visit(PAGE_URL)
    cy.get('#content', { timeout: 5000 }).should('be.visible')
  })

  // TC-01: Page loads with subjects and star rating buttons
  it('SD-T01 - Displays subjects with star rating buttons', () => {
    cy.get('.subject-item').should('have.length', 3)
    cy.get('.subject-item').first().within(() => {
      cy.contains('Mathematics')
      cy.get('.star-button').should('have.length', 5)
      cy.get('.star-button.active').should('have.length', 0)
    })
  })

  // TC-02: Clicking a star sets the correct rating
  it('SD-T02 - Clicking the 3rd star sets rating to 3', () => {
    cy.get('.subject-item').first().within(() => {
      cy.get('.star-button').eq(2).click()
      cy.get('.star-button.active').should('have.length', 3)
    })
  })

  // TC-03: Clicking the highest star (5) activates all stars
  it('SD-T03 - Clicking the 5th star activates all 5 stars', () => {
    cy.get('.subject-item').first().within(() => {
      cy.get('.star-button').eq(4).click()
      cy.get('.star-button.active').should('have.length', 5)
    })
  })

  // TC-04: Clicking a lower star after a higher one reduces the rating
  it('SD-T04 - Clicking a lower star reduces the rating', () => {
    cy.get('.subject-item').first().within(() => {
      cy.get('.star-button').eq(4).click()
      cy.get('.star-button.active').should('have.length', 5)
      cy.get('.star-button').eq(1).click()
      cy.get('.star-button.active').should('have.length', 2)
    })
  })

  // TC-05: Clicking the 1st star sets minimum rating of 1
  it('SD-T05 - Clicking the 1st star activates only 1 star', () => {
    cy.get('.subject-item').first().within(() => {
      cy.get('.star-button').eq(0).click()
      cy.get('.star-button.active').should('have.length', 1)
    })
  })

  // TC-06: Ratings are independent per subject
  it('SD-T06 - Rating is independent per subject', () => {
    cy.get('.subject-item').eq(0).within(() => {
      cy.get('.star-button').eq(2).click()
    })
    cy.get('.subject-item').eq(1).within(() => {
      cy.get('.star-button').eq(0).click()
    })
    cy.get('.subject-item').eq(0).within(() => {
      cy.get('.star-button.active').should('have.length', 3)
    })
    cy.get('.subject-item').eq(1).within(() => {
      cy.get('.star-button.active').should('have.length', 1)
    })
  })

  // TC-07: Deleting a subject removes it from the list
  it('SD-T07 - Deleting a subject removes it from the list', () => {
    cy.get('.subject-item').should('have.length', 3)
    cy.get('.subject-item').first().find('.btn-delete').click()
    cy.get('.subject-item').should('have.length', 2)
  })

  // TC-08: Deleting all subjects shows empty warning
  it('SD-T08 - Empty warning is shown when all subjects are deleted', () => {
    cy.get('.btn-delete').first().click()
    cy.get('.btn-delete').first().click()
    cy.get('.btn-delete').first().click()
    cy.get('.empty-warning').should('be.visible')
    cy.get('.subject-item').should('not.exist')
  })

  // TC-09: Adding a new subject appends it to the list
  it('SD-T09 - Can add a new subject via input', () => {
    cy.get('#new-subject-input').type('Chemistry')
    cy.get('#btn-add').click()
    cy.get('.subject-item').should('have.length', 4)
    cy.contains('.subject-item', 'Chemistry')
  })

  // TC-10: Newly added subject has 5 stars and none active
  it('SD-T10 - New subject has 5 star buttons with none active', () => {
    cy.get('#new-subject-input').type('Biology')
    cy.get('#btn-add').click()
    cy.get('.subject-item').last().within(() => {
      cy.contains('Biology')
      cy.get('.star-button').should('have.length', 5)
      cy.get('.star-button.active').should('have.length', 0)
    })
  })

  // TC-11: Adding subject via Enter key works
  it('SD-T11 - Adding subject via Enter key works', () => {
    cy.get('#new-subject-input').type('Enter Subject{enter}')
    cy.get('.subject-item').should('have.length', 4)
    cy.contains('.subject-item', 'Enter Subject')
  })

  // TC-12: View Events button shows success notice
  it('SD-T12 - View Events button triggers success message', () => {
    cy.get('#btn-events').click()
    cy.get('#save-notice')
      .should('have.class', 'success-message')
      .and('contain', 'Ratings saved successfully')
  })

  // TC-13: Star aria-labels are accessible
  it('SD-T13 - Star buttons have accessible aria-labels', () => {
    cy.get('.subject-item').first().within(() => {
      cy.get('.star-button').eq(0).should('have.attr', 'aria-label').and('include', '1 star')
      cy.get('.star-button').eq(4).should('have.attr', 'aria-label').and('include', '5 stars')
    })
  })

  // TC-14: Loading message is shown then hidden
  it('SD-T14 - Loading message is hidden after page loads', () => {
    cy.get('#loading-msg').should('not.be.visible')
    cy.get('#content').should('be.visible')
  })

  // TC-15: Subject numbers are sequential
  it('SD-T15 - Subject numbers are sequential starting from 1', () => {
    cy.get('.subject-item').eq(0).find('.number').should('have.text', '1.')
    cy.get('.subject-item').eq(1).find('.number').should('have.text', '2.')
    cy.get('.subject-item').eq(2).find('.number').should('have.text', '3.')
  })

})
