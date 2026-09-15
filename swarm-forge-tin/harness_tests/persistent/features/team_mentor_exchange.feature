Feature: Team mentor exchange

  # The worker and mentor talk over one fixed edge: worker -> mentor is an ask,
  # mentor -> worker is a brief. An ask is recorded as a stuck journal entry so
  # the oracle evidence travels with it; a brief is dialogue and is not
  # journaled. Done appends a done entry and reports the team queue empty.

  Background:
    Given a temporary project with its own state root
    And the orchestrator opens task "feature/periods" for role "coder"
    And the worker and mentor seats are bound to task "feature/periods"

  # Team mentor exchange 1 - an ask is recorded as a stuck entry
  Scenario Outline: Team mentor exchange 1 - an ask is recorded as a stuck entry
    When the "<seat>" seat sends kind "<kind>" with message "<message>"
    Then the chunk send reports "QUEUED: <kind>"
    And the chunk journal ends with kind "stuck"
    And the last journal entry records message "<message>"

    Examples:
      | seat   | kind | message                          |
      | worker | ask  | why does the parser reject this? |

  # Team mentor exchange 2 - a brief is not journaled
  Scenario Outline: Team mentor exchange 2 - a brief is not journaled
    When the "<seat>" seat sends kind "<kind>" with message "<message>"
    Then the chunk send reports "QUEUED: <kind>"
    And the chunk journal has one entry

    Examples:
      | seat   | kind  | message                |
      | mentor | brief | use the simpler design |

  # Team mentor exchange 3 - the wrong kind on the edge is refused
  Scenario Outline: Team mentor exchange 3 - the wrong kind on the edge is refused
    When the "<seat>" seat sends kind "<kind>" with message "<message>"
    Then the chunk send refusal names "<problem>"
    And the chunk journal has one entry

    Examples:
      | seat   | kind  | message | problem                                     |
      | worker | brief | hello   | edge worker -> mentor requires kind `ask`   |
      | mentor | ask   | hello   | edge mentor -> worker requires kind `brief` |

  # Team mentor exchange 4 - done records the completion and reports no task
  Scenario Outline: Team mentor exchange 4 - done records the completion and reports no task
    When the "<seat>" seat finishes its chunk
    Then the chunk completion reports "COMPLETED: <task>/<seat>"
    And the chunk completion reports "NO_TASK"
    And the last journal entry has kind "<kind>"

    Examples:
      | seat   | task            | kind |
      | worker | feature/periods | done |
