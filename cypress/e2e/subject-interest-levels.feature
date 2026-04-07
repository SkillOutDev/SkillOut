Feature: Subject interest level selection and persistence
  As a student
  I want to choose and save interest levels for subjects
  So that my preferences are stored correctly

  Background:
    Given I open the subject interest page
    And I clear previously saved subject ratings

  Scenario: First-time save with selected ratings
    When I set "Mathematics" to 5 stars
    And I set "Physics" to 3 stars
    And I save my subject ratings
    Then I should see a save confirmation message
    And "Mathematics" should show 5 stars
    And "Physics" should show 3 stars

  Scenario: Change a rating before saving
    When I set "Algorithms" to 2 stars
    And I set "Algorithms" to 4 stars
    And I save my subject ratings
    Then I should see a save confirmation message
    And "Algorithms" should show 4 stars

  Scenario: Save with no changes keeps default 0 stars
    When I save my subject ratings
    Then I should see a save confirmation message
    And all displayed subjects should show 0 stars
    And saved ratings should not contain null values

  Scenario: Multiple rapid save clicks do not break saving
    When I set "Databases" to 5 stars
    And I click save 3 times quickly
    Then I should see a save confirmation message
    And "Databases" should show 5 stars

  Scenario: Handle edge values and rapid rating changes
    When I quickly change "Operating Systems" to 1, 5, 2, 5 stars
    And I save my subject ratings
    Then I should see a save confirmation message
    And "Operating Systems" should show 5 stars

  Scenario: Selected rating cannot be nulled by re-clicking the same star
    When I set "Mathematics" to 5 stars
    And I click near the stars for "Mathematics"
    Then "Mathematics" should show 0 stars

  Scenario: Partial selection is saved while other subjects remain unrated
    When I set "Web Development" to 4 stars
    And I save my subject ratings
    Then I should see a save confirmation message
    And "Web Development" should show 4 stars
    And "Mathematics" should show 0 stars
    And saved ratings should not contain null values

  Scenario: Saved selections persist after page reload
    When I set "Mathematics" to 5 stars
    And I set "Physics" to 3 stars
    And I save my subject ratings
    And I reload the page
    Then "Mathematics" should show 5 stars
    And "Physics" should show 3 stars
    And saved ratings should not contain null values

  Scenario: Unsaved changes are lost after refresh
    Given I set and save "Data Structures" to 2 stars
    When I set "Data Structures" to 5 stars
    And I reload the page
    Then "Data Structures" should show 2 stars

  Scenario: Update previously saved ratings
    Given I set and save "Artificial Intelligence" to 2 stars
    When I set "Artificial Intelligence" to 5 stars
    And I save my subject ratings
    And I reload the page
    Then "Artificial Intelligence" should show 5 stars
