Feature: Team context delivery

  # A bound seat receives its assignment through context. A non-coder worker
  # gets the input pack plus the journal; --delta returns only the entries since
  # the seat's cursor; every delivery records an advice entry and advances the
  # cursor. A brief is dialogue and is never delivered by context.

  Background:
    Given a temporary project with its own state root
    And a brief file, a feature file, and a design file for the task
    And the orchestrator opens task "feature/periods" for role "refactorer" with those inputs
    And the worker seat is bound to task "feature/periods"

  # Team context delivery 1 - a non-coder worker gets the input pack and journal
  Scenario Outline: Team context delivery 1 - a non-coder worker gets the input pack and journal
    When the worker loads its context
    Then the context header names task "<task>" seat "<seat>" in "<mode>" mode
    And the context carries the input pack
    And the context carries the journal

    Examples:
      | task            | seat   | mode |
      | feature/periods | worker | full |

  # Team context delivery 2 - a full load records advice and advances the cursor
  Scenario Outline: Team context delivery 2 - a full load records advice and advances the cursor
    When the worker loads its context
    Then the last journal entry has kind "advice"
    And the last journal entry records mode "<mode>"
    And the status shows seat "<seat>" loaded "yes" with cursor "2"

    Examples:
      | seat   | mode |
      | worker | full |

  # Team context delivery 3 - delta returns only entries since the cursor
  Scenario Outline: Team context delivery 3 - delta returns only entries since the cursor
    Given the worker loads its context
    And the worker journals a "<kind>" entry
    When the worker loads a delta context
    Then the context header names task "<task>" seat "<seat>" in "<mode>" mode
    And the delta context carries the "<kind>" journal entry
    And the delta context omits the "open" journal entry

    Examples:
      | task            | seat   | mode  | kind |
      | feature/periods | worker | delta | plan |

  # Team context delivery 4 - delta before a full load is refused
  Scenario Outline: Team context delivery 4 - delta before a full load is refused
    When the worker loads a delta context
    Then the context refusal names "<problem>"
    And the last journal entry has kind "open"

    Examples:
      | problem       |
      | LOAD_REQUIRED |

  # Team context delivery 5 - dialogue is never delivered by context
  Scenario Outline: Team context delivery 5 - dialogue is never delivered by context
    Given the mentor seat is also bound
    And the mentor sends a brief "<message>"
    When the worker loads its context
    Then the context does not carry "<message>"

    Examples:
      | message                |
      | use the simpler design |
