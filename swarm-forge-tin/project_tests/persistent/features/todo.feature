Feature: Todo list

  Scenario: Adding a todo makes it pending
    Given an empty todo list
    When I add the todo "write the spec"
    Then the pending todos are "write the spec"
    And the completed todos are ""

  Scenario: Completing a todo moves it out of pending
    Given an empty todo list
    When I add the todo "write the spec"
    And I add the todo "write the code"
    And I complete the todo "write the spec"
    Then the pending todos are "write the code"
    And the completed todos are "write the spec"

  Scenario: Completing an unknown todo is an error
    Given an empty todo list
    When I complete the todo "missing"
    Then the operation fails with "unknown todo: missing"

  Scenario: Adding a blank todo is an error
    Given an empty todo list
    When I add the todo ""
    Then the operation fails with "title must not be blank"
