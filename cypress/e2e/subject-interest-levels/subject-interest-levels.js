const {
  Given,
  When,
  Then,
} = require("@badeball/cypress-cucumber-preprocessor");

const normalize = (subjectName) =>
  subjectName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

const candidateSelectors = {
  saveButton: [
    '[data-testid="save-button"]',
    'button[data-testid="save-button"]',
    'button:contains("Save")',
  ],
  successMessage: [
    '[data-testid="success-message"]',
    '.success-message',
    '#successMessage',
  ],
};

function withBody(fn) {
  cy.get("body").then(($body) => fn($body));
}

function findFirstFromBody($body, selectors) {
  return selectors.find((selector) => {
    if (selector.includes(":contains(")) {
      return false;
    }
    return $body.find(selector).length > 0;
  });
}

function subjectRowSelectors(subjectName) {
  const slug = normalize(subjectName);
  return [
    `[data-testid="subject-${slug}"]`,
    `[data-testid="subject-${subjectName}"]`,
  ];
}

function ratingValueSelectors(subjectName) {
  const slug = normalize(subjectName);
  return [
    `[data-testid="${slug}-rating-value"]`,
    `[data-testid="rating-${slug}"]`,
    `#rating-${slug}`,
  ];
}

function getSubjectRoot(subjectName) {
  return cy.get("body").then(($body) => {
    const rowMatch = findFirstFromBody($body, subjectRowSelectors(subjectName));
    if (rowMatch) {
      return cy.get(rowMatch).first();
    }

    return cy.contains(".subject-name", subjectName).closest(".subject-item");
  });
}

function clickStar(subjectName, starCount) {
  if (starCount < 1 || starCount > 5) {
    return;
  }

  getSubjectRoot(subjectName).within(() => {
    const directByTestId = `[data-testid="star-${starCount}"]`;
    const directByValue = `.star[data-value="${starCount}"]`;

    cy.root().then(($root) => {
      if ($root.find(directByTestId).length > 0) {
        cy.get(directByTestId).first().click({ force: true });
      } else if ($root.find(directByValue).length > 0) {
        cy.get(directByValue).first().click({ force: true });
      } else {
        cy.get('.star, [data-testid^="star-"]')
          .eq(starCount - 1)
          .click({ force: true });
      }
    });
  });
}

function assertSubjectRating(subjectName, expectedStars) {
  getSubjectRoot(subjectName).within(() => {
    const valueSelectors = ratingValueSelectors(subjectName);

    cy.root().then(($root) => {
      const ratingValueSelector = valueSelectors.find(
        (selector) => $root.find(selector).length > 0
      );

      if (ratingValueSelector) {
        cy.get(ratingValueSelector)
          .first()
          .should("contain", String(expectedStars));
      } else {
        const fallbackSelector =
          $root.find(".rating-value").length > 0
            ? ".rating-value"
            : "[data-testid$='rating-value']";

        cy.get(fallbackSelector).first().should("contain", String(expectedStars));
      }
    });
  });
}

function clickSaveButton() {
  withBody(($body) => {
    const selector = findFirstFromBody($body, candidateSelectors.saveButton);

    if (selector) {
      cy.get(selector).first().click({ force: true });
    } else {
      cy.contains("button", /save/i).click({ force: true });
    }
  });
}

Given("I open the subject interest page", () => {
  cy.visit("cypress/fixtures/subject-interest-page.html");
});

Given("I clear previously saved subject ratings", () => {
  cy.window().then((win) => {
    win.localStorage.removeItem("subjectRatings");
  });
  cy.reload();
});

When("I set {string} to {int} stars", (subjectName, stars) => {
  if (stars < 0 || stars > 5) {
    throw new Error("Only ratings from 0 to 5 are supported.");
  }
  if (stars === 0) {
    return;
  }
  clickStar(subjectName, stars);
});

When(
  "I quickly change {string} to {int}, {int}, {int}, {int} stars",
  (subjectName, a, b, c, d) => {
    [a, b, c, d].forEach((stars) => clickStar(subjectName, stars));
  }
);

When("I save my subject ratings", () => {
  clickSaveButton();
});

When("I click save {int} times quickly", (times) => {
  Cypress._.times(times, () => clickSaveButton());
});

When("I click near the stars for {string}", (subjectName) => {
  getSubjectRoot(subjectName).within(() => {
    cy.get(".star-rating").click("right", { force: true });
  });
});

When("I reload the page", () => {
  cy.reload();
});

Given("I set and save {string} to {int} stars", (subjectName, stars) => {
  if (stars > 0) {
    clickStar(subjectName, stars);
  }
  clickSaveButton();
});

Then("I should see a save confirmation message", () => {
  withBody(($body) => {
    const selector = findFirstFromBody($body, candidateSelectors.successMessage);

    if (selector) {
      cy.get(selector).should("have.class", "show");
      return;
    }

    cy.contains(/saved|success/i).should("be.visible");
  });
});

Then("{string} should show {int} stars", (subjectName, stars) => {
  assertSubjectRating(subjectName, stars);
});

Then("all displayed subjects should show 0 stars", () => {
  cy.get(".rating-value, [data-testid$='rating-value']").each(($el) => {
    cy.wrap($el).should("contain", "0");
  });
});

Then("saved ratings should not contain null values", () => {
  cy.window().then((win) => {
    const raw = win.localStorage.getItem("subjectRatings");
    const parsed = JSON.parse(raw || "{}");

    Object.values(parsed).forEach((value) => {
      expect(value, "saved rating should not be null").to.not.equal(null);
      expect(Number(value), "saved rating should be >= 0").to.be.at.least(0);
      expect(Number(value), "saved rating should be <= 5").to.be.at.most(5);
    });
  });
});
