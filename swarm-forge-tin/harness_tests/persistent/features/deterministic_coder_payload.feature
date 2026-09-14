Feature: Deterministic coder payload

  # A bound coder calls team_context to receive its assignment. The payload is
  # assembled only from the task's task.json and the resolved harness config, so
  # the coder never discovers paths or guesses what to do.

  Background:
    Given a bound coder with a task and a harness config

  # Deterministic coder payload 1 - the payload has the fixed sections in order
  Scenario Outline: Deterministic coder payload 1 - the payload has the fixed sections in order
    When the coder calls team_context
    Then payload section <position> is "<section>"

    Examples:
      | position | section            |
      | 1        | TASK               |
      | 2        | DEFINITION OF DONE |
      | 3        | RESOLVED PATHS     |
      | 4        | INPUTS             |
      | 5        | FEATURE            |
      | 6        | INTERFACE CONTRACT |
      | 7        | FILES              |
      | 8        | HOW TO RUN         |
      | 9        | PRIOR ATTEMPT      |
      | 10       | WHEN STUCK         |
      | 11       | WHEN DONE          |

  # Deterministic coder payload 2 - the payload has exactly the fixed sections
  Scenario: Deterministic coder payload 2 - the payload has exactly the fixed sections
    When the coder calls team_context
    Then the payload has exactly 11 sections

  # Deterministic coder payload 3 - the payload comes from task.json
  Scenario Outline: Deterministic coder payload 3 - the payload comes from task.json
    Given the task name is "<task>"
    And the task definition of done is "<done>"
    When the coder calls team_context
    Then the TASK section names task "<task>"
    And the DEFINITION OF DONE section carries "<done>"

    Examples:
      | task                | done                            |
      | feature/periods     | the persistent tests pass       |
      | bug/leap-year-crash | a regression test proves the fix |

  # Deterministic coder payload 4 - resolved paths come from the harness config, not the disk
  Scenario Outline: Deterministic coder payload 4 - resolved paths come from the harness config, not the disk
    Given the harness config sets the <setting> to "<location>"
    And no directory exists at "<location>"
    When the coder calls team_context
    Then the RESOLVED PATHS section reports the <setting> as "<location>"

    Examples:
      | setting              | location               |
      | workspace root       | /absent/project        |
      | state root           | /absent/project/.state |
      | artifacts root       | /absent/project/dump   |
      | hot tests root       | /absent/project/hot    |
      | persistent test root | /absent/project/tests  |

  # Deterministic coder payload 5 - the payload is stable across calls
  Scenario: Deterministic coder payload 5 - the payload is stable across calls
    When the coder calls team_context
    Then calling team_context again yields the same payload
