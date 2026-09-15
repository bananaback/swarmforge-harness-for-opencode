Feature: Team recovery

  # A bound session still resolves its chunk after the UTC date rolls over, a
  # repeated done only appends, and a corrupt task record fails closed.

  Background:
    Given a temporary project with its own state root

  # Team recovery 1 - context resolves a task filed under an earlier date
  Scenario: Team recovery 1 - context resolves a task filed under an earlier date
    Given the orchestrator opens task "feature/periods" for role "coder"
    And the worker seat is bound to task "feature/periods"
    And the task is filed under the previous UTC date
    When the worker loads its context
    Then the context header names task "feature/periods" seat "worker" in "full" mode

  # Team recovery 2 - done resolves a task filed under an earlier date
  Scenario: Team recovery 2 - done resolves a task filed under an earlier date
    Given the orchestrator opens task "feature/periods" for role "coder"
    And the worker seat is bound to task "feature/periods"
    And the task is filed under the previous UTC date
    When the "worker" seat finishes its chunk
    Then the chunk completion reports "COMPLETED: feature/periods/worker"
    And the chunk completion reports "NO_TASK"

  # Team recovery 3 - a repeated done still reports the task complete
  Scenario: Team recovery 3 - a repeated done still reports the task complete
    Given the orchestrator opens task "feature/periods" for role "coder"
    And the worker seat is bound to task "feature/periods"
    And the "worker" seat finishes its chunk
    When the "worker" seat calls done again
    Then the chunk completion reports "NO_TASK"
    And the chunk journal ends with kind "done"

  # Team recovery 4 - a corrupt task record fails closed
  Scenario: Team recovery 4 - a corrupt task record fails closed
    Given the orchestrator opens task "feature/periods" for role "coder"
    And the task record is corrupted
    When session "worker-1" binds to seat "worker" of task "feature/periods"
    Then the bind refusal names "corrupt"
