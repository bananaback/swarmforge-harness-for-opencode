Feature: Task-breaker bridge

  # The task-breaker agent emits a chunk plan. The bridge validates the whole
  # plan, stages each chunk's brief and design under the artifacts root, and
  # opens one team task per entry. Validation is all-or-nothing: any problem
  # refuses the plan and opens nothing.

  Background:
    Given a temporary project with its own state root

  # Task-breaker bridge 1 - a valid chunk opens its team task
  Scenario Outline: Task-breaker bridge 1 - a valid chunk opens its team task
    Given a task-breaker plan with a valid chunk "<task>" for role "<role>"
    When the task-breaker plan is opened
    Then the bridge reports the opened tasks "<task>"
    And team task "<task>" exists for role "<role>"

    Examples:
      | task        | role       |
      | cart-domain | coder      |
      | cart-repo   | refactorer |

  # Task-breaker bridge 2 - a plan opens one team task per chunk
  Scenario: Task-breaker bridge 2 - a plan opens one team task per chunk
    Given a task-breaker plan with a valid chunk "cart-domain" for role "coder"
    And the plan holds another valid chunk "cart-repo" for role "refactorer"
    When the task-breaker plan is opened
    Then the bridge reports the opened tasks "cart-domain, cart-repo"

  # Task-breaker bridge 3 - the chunk fields reach the opened task
  Scenario Outline: Task-breaker bridge 3 - the chunk fields reach the opened task
    Given a task-breaker plan with a valid chunk "cart-domain" for role "coder"
    When the task-breaker plan is opened
    Then the opened task records <field> "<value>"

    Examples:
      | field              | value                     |
      | definition of done | - [ ] total               |
      | interface contract | class Cart: ...           |
      | files              | - src/cart.py -- Cart     |
      | mentor goal        | make the cart total green |
      | mentor rules       | one job per method        |

  # Task-breaker bridge 4 - a plan with no chunks is refused
  Scenario: Task-breaker bridge 4 - a plan with no chunks is refused
    Given a task-breaker plan with no chunks
    When the task-breaker plan is opened
    Then the bridge is refused with a problem naming "plan requires a non-empty `chunks` list"
    And the bridge opens nothing

  # Task-breaker bridge 5 - a duplicated task is refused
  Scenario Outline: Task-breaker bridge 5 - a duplicated task is refused
    Given a task-breaker plan with a duplicated task "<task>"
    When the task-breaker plan is opened
    Then the bridge is refused with a problem naming "<problem>"
    And the bridge opens nothing

    Examples:
      | task        | problem                                  |
      | cart-domain | chunk 2 task `cart-domain` is duplicated |

  # Task-breaker bridge 6 - an unsupported role is refused
  Scenario Outline: Task-breaker bridge 6 - an unsupported role is refused
    Given a task-breaker plan with an unsupported role "<role>"
    When the task-breaker plan is opened
    Then the bridge is refused with a problem naming "<problem>"
    And the bridge opens nothing

    Examples:
      | role     | problem                                                    |
      | designer | chunk 1 role must be one of: coder, refactorer, architect |

  # Task-breaker bridge 7 - a brief-less chunk refuses the whole plan
  Scenario: Task-breaker bridge 7 - a brief-less chunk refuses the whole plan
    Given a task-breaker plan with a valid chunk "cart-domain" for role "coder"
    And the plan holds a brief-less chunk
    When the task-breaker plan is opened
    Then the bridge is refused with a problem naming "requires `brief_text` or `brief`"
    And the bridge opens nothing

  # Task-breaker bridge 8 - a design-less chunk is accepted
  Scenario Outline: Task-breaker bridge 8 - a design-less chunk is accepted
    Given a task-breaker plan with a design-less chunk "<task>" for role "<role>"
    When the task-breaker plan is opened
    Then the bridge reports the opened tasks "<task>"

    Examples:
      | task        | role  |
      | cart-domain | coder |

  # Task-breaker bridge 9 - a missing referenced input is refused
  Scenario Outline: Task-breaker bridge 9 - a missing referenced input is refused
    Given a task-breaker plan referencing a missing "<reference>"
    When the task-breaker plan is opened
    Then the bridge is refused with a problem naming "<problem>"
    And the bridge opens nothing

    Examples:
      | reference | problem                                     |
      | brief     | chunk 1 brief not found: missing.brief.md   |
      | feature   | feature not found: features/missing.feature |

  # Task-breaker bridge 10 - staged inputs land under the artifacts root
  Scenario: Task-breaker bridge 10 - staged inputs land under the artifacts root
    Given a task-breaker plan with a valid chunk "cart-domain" for role "coder"
    When the task-breaker plan is opened
    Then the staged inputs land under "taskbreak/cart.plan"
    And the staged brief "01-cart-domain.brief.md" carries exactly one ORACLE section
    And the staged design "01-cart-domain.design.md" exists

  # Task-breaker bridge 11 - an existing ORACLE section is preserved
  Scenario: Task-breaker bridge 11 - an existing ORACLE section is preserved
    Given a task-breaker plan whose chunk brief already carries an oracle
    When the task-breaker plan is opened
    Then the staged brief "01-cart-domain.brief.md" carries exactly one ORACLE section

  # Task-breaker bridge 12 - a dry run stages the inputs without opening
  Scenario: Task-breaker bridge 12 - a dry run stages the inputs without opening
    Given a task-breaker plan with a valid chunk "cart-domain" for role "coder"
    When the task-breaker plan is opened as a dry run
    Then the staged inputs land under "taskbreak/cart.plan"
    And the bridge reports "DRY RUN: no chunks opened"
    And the bridge opens nothing

  # Task-breaker bridge 13 - JSON output names the opened tasks
  Scenario: Task-breaker bridge 13 - JSON output names the opened tasks
    Given a task-breaker plan with a valid chunk "cart-domain" for role "coder"
    When the task-breaker plan is opened with JSON output
    Then the bridge emits JSON naming the opened tasks "cart-domain"

  # Task-breaker bridge 14 - a chunk feature overrides the plan feature
  Scenario: Task-breaker bridge 14 - a chunk feature overrides the plan feature
    Given a task-breaker plan whose chunk overrides the plan feature
    When the task-breaker plan is opened
    Then the chunk input holds only the feature "other.feature"

  # Task-breaker bridge 15 - a plan that is not valid JSON is refused
  Scenario: Task-breaker bridge 15 - a plan that is not valid JSON is refused
    Given a task-breaker plan that is not valid JSON
    When the task-breaker plan is opened
    Then the bridge is refused with a problem naming "plan is not valid JSON"
    And the bridge opens nothing

  # Task-breaker bridge 16 - an unsupported plan version is refused
  Scenario Outline: Task-breaker bridge 16 - an unsupported plan version is refused
    Given a task-breaker plan with schema version "<version>"
    When the task-breaker plan is opened
    Then the bridge is refused with a problem naming "<problem>"
    And the bridge opens nothing

    Examples:
      | version | problem                |
      | 2       | plan version must be 1 |
