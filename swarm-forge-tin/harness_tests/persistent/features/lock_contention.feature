Feature: Lock contention

  # Two operating-system processes contend on the same mail or team lock. The
  # exclusive advisory lock serializes them, so queue deduplication and journal
  # appends stay consistent and each process observes the other's committed
  # state.

  Background:
    Given a temporary project with its own state root

  # Lock contention 1 - concurrent identical sends queue exactly one item
  Scenario: Lock contention 1 - concurrent identical sends queue exactly one item
    When two identical handoffs for task "feature/periods" are sent to "coder" at the same time
    Then exactly one send queues the item
    And the "coder" mailbox queued count is "1"

  # Lock contention 2 - concurrent journal appends keep distinct sequence numbers
  Scenario: Lock contention 2 - concurrent journal appends keep distinct sequence numbers
    Given the orchestrator opens task "feature/periods" for role "coder"
    And the worker seat is bound to task "feature/periods"
    When the "worker" seat appends a "plan" entry and a "result" entry at the same time
    Then the chunk journal records a "plan" entry and a "result" entry with distinct sequence numbers
