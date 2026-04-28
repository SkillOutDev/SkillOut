describe('Studijų dalykų valdymo testai', () => {
  beforeEach(() => {
    // API imitacijos (mocks)
    cy.intercept('GET', '/api/get-latest-subjects/', {
      body: { study_subjects: ['Matematika', 'Fizika'] }
    }).as('getSubjects');

    cy.intercept('GET', '/api/student/1/subjects/', {
      body: { subjects: [] }
    }).as('getStudentSubjects');

    cy.visit('/subjects');
    cy.wait(['@getSubjects', '@getStudentSubjects']);
  });

  it('SD-T122: Naujo studijų dalyko pridėjimas į sąrašą', () => {
    const naujasDalykas = 'Programavimas';

    // Įvedame pavadinimą į input lauką
    cy.get('input.input-add').type(naujasDalykas);
    
    // Spaudžiame "Add Subject" mygtuką
    cy.get('.btn-add').click();

    // Patikriname, ar dalykas atsirado sąraše (vizualiai)
    cy.get('.subjects-list').should('contain', naujasDalykas);
    // Patikriname, ar input laukas tapo tuščias
    cy.get('input.input-add').should('have.value', '');
  });

  it('SD-T121: Studijų dalyko ištrynimas naudojant ikonėlę', () => {
    // Patikriname, ar pradiniai elementai egzistuoja
    cy.get('.subject-item').should('have.length', 2);

    // Spaudžiame šiukšliadėžės ikoną (🗑️) pirmam elementui
    cy.get('.btn-delete').first().click();

    // Patikriname, ar sąrašas sumažėjo iki 1 elemento
    cy.get('.subject-item').should('have.length', 1);
    cy.get('.subjects-list').should('not.contain', 'Matematika');
  });

  it('SD-T123: Sistemos įspėjimas esant tuščiam sąrašui', () => {
    // 1. Pirmiausia sužinome kiek iš viso yra šiukšliadėžės mygtukų
    cy.get('.btn-delete').then(($btns) => {
      const kiekis = $btns.length;

      // 2. Spaudžiame "pirmą" mygtuką tiek kartų, kiek jų buvo
      // Naudojame paprastą ciklą, kad kaskart iš naujo surastume elementą DOM'e
      for (let i = 0; i < kiekis; i++) {
        cy.get('.btn-delete').first().click();
      }
    });

    // 3. Patikriname, ar sąrašas dingo
    cy.get('.subjects-list').should('not.exist');

    // 4. Patikriname, ar rodomas tuščio sąrašo įspėjimas
    cy.get('.empty-warning')
      .should('be.visible')
      .and('contain', 'List is empty!');
  });
});