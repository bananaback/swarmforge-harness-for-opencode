Feature: Deterministic mentor payload

  # A bound mentor calls team_context to receive its advisory context. The
  # payload is a system prompt plus GOAL, RULES, TRAIL, ASK, and verbatim
  # FAILURE evidence, assembled from the task and chunk state without a model.

  Background:
    Given a bound mentor with a task and a chunk state

  # Deterministic mentor payload 1 - the payload leads with a system prompt
  Scenario: Deterministic mentor payload 1 - the payload leads with a system prompt
    When the mentor calls team_context
    Then the payload starts with a system prompt
    And the payload has exactly 5 mentor sections

  # Deterministic mentor payload 2 - the payload has the fixed sections in order
  Scenario Outline: Deterministic mentor payload 2 - the payload has the fixed sections in order
    When the mentor calls team_context
    Then mentor section <position> is "<section>"

    Examples:
      | position | section |
      | 1        | GOAL    |
      | 2        | RULES   |
      | 3        | TRAIL   |
      | 4        | ASK     |
      | 5        | FAILURE |

  # Deterministic mentor payload 3 - each section carries its chunk state value
  Scenario Outline: Deterministic mentor payload 3 - each section carries its chunk state value
    Given the chunk state sets <section> to "<value>"
    When the mentor calls team_context
    Then the "<section>" section carries "<value>"

    Examples:
      | section | value                            |
      | GOAL    | fix the failing acceptance tests |
      | RULES   | never edit the feature file      |
      | ASK     | why does the parser reject this? |

  # Deterministic mentor payload 4 - the TRAIL section lists the worker journal in order
  Scenario: Deterministic mentor payload 4 - the TRAIL section lists the worker journal in order
    Given the worker journaled a plan and a result
    When the mentor calls team_context
    Then the TRAIL section lists both journal entries in order

  # Deterministic mentor payload 5 - the FAILURE section reproduces the evidence verbatim
  Scenario Outline: Deterministic mentor payload 5 - the FAILURE section reproduces the evidence verbatim
    Given the worker recorded a failure with evidence "<evidence>"
    When the mentor calls team_context
    Then the FAILURE section reproduces the evidence verbatim

    Examples:
      | evidence                                   |
      | AssertionError: expected 3 got 2           |
      | Traceback line 42 -> boom; retry exhausted |

  # Deterministic mentor payload 6 - the payload is assembled without a model call
  Scenario: Deterministic mentor payload 6 - the payload is assembled without a model call
    Given a model stub that records calls
    When the mentor calls team_context
    Then no model request was made

  # Deterministic mentor payload 7 - the payload is stable across calls
  Scenario: Deterministic mentor payload 7 - the payload is stable across calls
    When the mentor calls team_context
    Then calling team_context again yields the same payload
