Feature: Team write-once input

  # A chunk's input/ is the immutable assignment: open copies the brief,
  # feature, design, and parsed IR once, and no later team operation rewrites or
  # adds to it. Reopening the task cannot overwrite the copy either, and editing
  # the source after open never reaches the chunk.

  Background:
    Given a temporary project with its own state root
    And a brief file, a feature file, and a design file for the task
    And the orchestrator opens task "feature/periods" for role "coder" with those inputs
    And the worker seat is bound to task "feature/periods"
    And the chunk input is snapshotted

  # Team write-once input 1 - an operation leaves the input pack unchanged
  Scenario Outline: Team write-once input 1 - an operation leaves the input pack unchanged
    When the worker performs the "<operation>" operation
    Then the chunk input matches the snapshot

    Examples:
      | operation      |
      | pull           |
      | context        |
      | journal        |
      | oracle attempt |
      | mentor ask     |
      | done           |

  # Team write-once input 2 - reopening the task cannot overwrite the inputs
  Scenario Outline: Team write-once input 2 - reopening the task cannot overwrite the inputs
    When the orchestrator tries to reopen task "<task>" for role "<role>"
    Then the reopen refusal names "<problem>"
    And the chunk input matches the snapshot

    Examples:
      | task            | role  | problem                                                |
      | feature/periods | coder | task `feature/periods` already exists for role `coder` |

  # Team write-once input 3 - editing the source after open does not change the copy
  Scenario: Team write-once input 3 - editing the source after open does not change the copy
    When the given brief file is edited
    Then the chunk input matches the snapshot
