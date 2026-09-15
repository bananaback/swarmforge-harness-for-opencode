Feature: Team command validation

  # team validates a command's role, task name, and seat before touching state,
  # and only the worker seat may append worker journal kinds.

  Background:
    Given a temporary project with its own state root

  # Team command validation 1 - open rejects an unknown role
  Scenario Outline: Team command validation 1 - open rejects an unknown role
    When the orchestrator attempts to open task "<task>" for role "<role>"
    Then the team refusal names "<problem>"

    Examples:
      | task | role    | problem |
      | c1   | manager | role must be one of: orchestrator, specifier, designer, task-breaker, coder, refactorer, architect, mentor |

  # Team command validation 2 - open rejects an invalid task name
  Scenario Outline: Team command validation 2 - open rejects an invalid task name
    When the orchestrator attempts to open task "<task>" for role "<role>"
    Then the team refusal names "<problem>"

    Examples:
      | task     | role  | problem |
      | /leading | coder | task must be a relative path without empty segments |

  # Team command validation 3 - bind rejects an unknown seat
  Scenario Outline: Team command validation 3 - bind rejects an unknown seat
    Given the orchestrator opens task "c1" for role "coder"
    When session "<session>" binds to seat "<seat>" of task "c1"
    Then the bind refusal names "<problem>"

    Examples:
      | session  | seat    | problem |
      | worker-1 | captain | seat must be one of: worker, mentor |

  # Team command validation 4 - only the worker seat may append worker journal kinds
  Scenario Outline: Team command validation 4 - only the worker seat may append worker journal kinds
    Given the orchestrator opens task "feature/periods" for role "coder"
    And the worker and mentor seats are bound to task "feature/periods"
    When the mentor seat journals a "<kind>" entry
    Then journaling fails
    And the chunk journal has one entry

    Examples:
      | kind |
      | plan |
