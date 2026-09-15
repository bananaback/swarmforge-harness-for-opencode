Feature: Team oracle attempt

  # The worker runs the oracle through the tool, never by hand. Each attempt
  # writes the captured output (and the git diff when the tree is dirty), bumps
  # the attempt counter, and appends an attempt journal entry. A journal entry
  # can attach an earlier attempt's facts by number. A timeout kills the oracle
  # and records exit 124.

  Background:
    Given a temporary project with its own state root
    And the orchestrator opens task "feature/periods" for role "coder"
    And the worker seat is bound to task "feature/periods"

  # Team oracle attempt 1 - the attempt prints its counter, exit, and cwd
  Scenario Outline: Team oracle attempt 1 - the attempt prints its counter, exit, and cwd
    When the worker runs the oracle command "<command>"
    Then the attempt reports "ATTEMPT: <attempt>"
    And the attempt reports "EXIT: <exit>"
    And the attempt reports "CWD: "
    And the attempt output carries "<output>"

    Examples:
      | command                | attempt | exit | output |
      | python3 -c 'print(42)' | 1       | 0    | 42     |

  # Team oracle attempt 2 - the attempt records its output and journal entry
  Scenario Outline: Team oracle attempt 2 - the attempt records its output and journal entry
    When the worker runs the oracle command "<command>"
    Then the chunk output holds "<name>"
    And the chunk output file "<name>" carries "<output>"
    And the last journal entry has kind "<kind>"
    And the last journal entry records exit "<exit>"

    Examples:
      | command                | name           | output | kind    | exit |
      | python3 -c 'print(42)' | attempt-01.txt | 42     | attempt | 0    |

  # Team oracle attempt 3 - a dirty tree records a diff
  Scenario Outline: Team oracle attempt 3 - a dirty tree records a diff
    Given the workspace has an uncommitted change
    When the worker runs the oracle command "<command>"
    Then the chunk output holds "<name>"

    Examples:
      | command               | name            |
      | python3 -c 'print(1)' | attempt-01.diff |

  # Team oracle attempt 4 - the attempt counter advances
  Scenario Outline: Team oracle attempt 4 - the attempt counter advances
    When the worker runs two oracle commands
    Then the chunk output holds "<name>"

    Examples:
      | name           |
      | attempt-02.txt |

  # Team oracle attempt 5 - a timeout is killed and recorded as exit 124
  Scenario Outline: Team oracle attempt 5 - a timeout is killed and recorded as exit 124
    When the worker runs the oracle command "<command>" with a "<timeout>" second timeout
    Then the attempt reports "EXIT: <exit>"
    And the last journal entry records exit "<exit>"

    Examples:
      | command  | timeout | exit |
      | sleep 30 | 0.5     | 124  |

  # Team oracle attempt 6 - a journal entry attaches an attempt's facts
  Scenario Outline: Team oracle attempt 6 - a journal entry attaches an attempt's facts
    Given the worker runs the oracle command "<command>"
    When the worker journals a "<kind>" entry attaching attempt "<attempt>"
    Then the last journal entry has kind "<kind>"
    And the last journal entry records exit "<exit>"

    Examples:
      | command               | kind   | attempt | exit |
      | python3 -c 'print(7)' | result | 1       | 0    |

  # Team oracle attempt 7 - attaching an unknown attempt is refused
  Scenario Outline: Team oracle attempt 7 - attaching an unknown attempt is refused
    Given the worker runs the oracle command "<command>"
    When the worker journals a "<kind>" entry attaching attempt "<attempt>"
    Then journaling fails
    And the chunk journal ends with kind "attempt"

    Examples:
      | command               | kind   | attempt |
      | python3 -c 'print(7)' | result | 9       |
