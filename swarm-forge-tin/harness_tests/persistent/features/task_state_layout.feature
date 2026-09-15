Feature: Task state layout and journal

  # Live work is grouped by UTC open date; each task is one self-contained folder;
  # each chunk is one role's turn with input, journal, and output.

  Background:
    Given a temporary project with its own state root

  # Task state layout 1 - opening a task creates the dated chunk layout
  Scenario Outline: Task state layout 1 - opening a task creates the dated chunk layout
    When the orchestrator opens task "<task>" for role "<role>"
    Then the task folder is filed under the opening UTC date
    And the task folder holds exactly task.json and one chunk folder for role "<role>"
    And the chunk folder holds exactly input, journal, and output

    Examples:
      | task                | role      |
      | feature/periods     | coder     |
      | bug/leap-year-crash | architect |

  # Task state layout 2 - opening a task copies the given inputs
  Scenario Outline: Task state layout 2 - opening a task copies the given inputs
    Given a brief file, a feature file, and a design file for the task
    When the orchestrator opens task "<task>" for role "<role>" with those inputs
    Then the chunk input folder holds a copy of each given file
    And the chunk input folder holds the parsed feature IR
    And every copied input matches its given file

    Examples:
      | task                | role       |
      | feature/periods     | coder      |
      | bug/leap-year-crash | refactorer |

  # Task state layout 3 - the open entry records the starting state
  Scenario Outline: Task state layout 3 - the open entry records the starting state
    Given a brief file, a feature file, and a design file for the task
    When the orchestrator opens task "<task>" for role "<role>" with those inputs
    Then the chunk journal has one entry
    And the first journal entry has kind "open"
    And the open entry records the git branch and commit
    And the open entry lists the given inputs

    Examples:
      | task                | role       |
      | feature/periods     | coder      |
      | bug/leap-year-crash | refactorer |

  # Task state layout 4 - worker journal kinds are accepted
  Scenario Outline: Task state layout 4 - worker journal kinds are accepted
    Given an open task "feature/periods" bound to a worker
    When the worker journals kind "<kind>"
    Then the last journal entry has kind "<kind>"

    Examples:
      | kind     |
      | readback |
      | plan     |
      | result   |
      | note     |

  # Task state layout 5 - an unknown journal kind is refused
  Scenario: Task state layout 5 - an unknown journal kind is refused
    Given an open task "feature/periods" bound to a worker
    When the worker requests an unsupported journal kind
    Then journaling fails
    And the chunk journal is unchanged

  # Task state layout 6 - tool operations record their tool kinds
  Scenario Outline: Task state layout 6 - tool operations record their tool kinds
    Given an open task "feature/periods" bound to a worker
    When the "<operation>" operation runs
    Then the last journal entry has kind "<kind>"

    Examples:
      | operation      | kind    |
      | oracle attempt | attempt |
      | mentor ask     | stuck   |
      | mentor brief   | advice  |
      | task done      | done    |

  # Task state layout 7 - the journal only grows in order
  Scenario: Task state layout 7 - the journal only grows in order
    Given an open task "feature/periods" bound to a worker
    And the worker has journaled a readback
    When the worker appends a plan entry
    Then the chunk journal has two entries
    And the journal entries are ordered by increasing sequence
    And the readback entry is unchanged

  # Task state layout 8 - closing with preserve moves the task to done
  Scenario: Task state layout 8 - closing with preserve moves the task to done
    Given an open task "feature/periods" bound to a worker
    And the worker records an oracle attempt
    When the orchestrator preserves task "feature/periods" by closing it
    Then the task folder "feature/periods" is gone from the live tasks
    And the task folder "feature/periods" appears whole under done
    And the preserved journal holds the same entries as before closing
    And the preserved output holds the attempt artifact

  # Task state layout 9 - closing without preserve deletes exactly that task
  Scenario: Task state layout 9 - closing without preserve deletes exactly that task
    Given an open task "feature/periods" bound to a worker
    And an open task "bug/leap-year-crash" bound to a worker
    When the orchestrator closes task "feature/periods" without preserve
    Then the task folder "feature/periods" is gone from the live tasks
    And the task folder "bug/leap-year-crash" is untouched
    And the live date folder remains

  # Task state layout 10 - closing without preserve removes an emptied date folder
  Scenario: Task state layout 10 - closing without preserve removes an emptied date folder
    Given an open task "feature/periods" bound to a worker
    When the orchestrator closes task "feature/periods" without preserve
    Then the task folder "feature/periods" is gone from the live tasks
    And the live date folder is gone

  # Task state layout 11 - the task record omits the dead seal flag
  # Rationale: `sealed` was never set and its `task is sealed` guards were dead,
  # so the field and the guards are removed instead of kept as a phantom.
  Scenario: Task state layout 11 - the task record omits the dead seal flag
    Given an open task "feature/periods" bound to a worker
    Then the task record has no seal flag

  # Task state layout 12 - bind finds a task filed under an earlier date
  # Rationale: bind resolved the task under today's UTC date and stranded a task
  # opened before midnight, so it now searches the live date folders.
  Scenario: Task state layout 12 - bind finds a task filed under an earlier date
    Given the orchestrator opens task "feature/periods" for role "coder"
    And the task is filed under the previous UTC date
    When session "worker-1" binds to seat "worker" of task "feature/periods"
    Then the bind reports "BOUND"

  # Task state layout 13 - close finds a task filed under an earlier date
  # Rationale: close resolved the task under today's UTC date and stranded a task
  # opened before midnight, so it now searches the live date folders.
  Scenario: Task state layout 13 - close finds a task filed under an earlier date
    Given an open task "feature/periods" bound to a worker
    And the task is filed under the previous UTC date
    When the orchestrator closes task "feature/periods" without preserve
    Then the task folder "feature/periods" is gone from the live tasks
