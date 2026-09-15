Feature: Mail recovery

  # The queue survives interrupted and duplicate work. A completed item is never
  # re-claimed, a dispatch after completion is a new item, and a corrupt item
  # fails closed: the tool reports an error and moves nothing.

  Background:
    Given a temporary project with its own state root

  # Mail recovery 1 - a completion without an in-process item is refused
  Scenario: Mail recovery 1 - a completion without an in-process item is refused
    Given mails "feature/periods@50" are queued to "coder"
    When "coder" completes its mail with result "green"
    Then the completion refusal names "no in-process mail"
    And the "coder" mailbox queued count is "1"

  # Mail recovery 2 - a completed item is not re-claimed
  Scenario: Mail recovery 2 - a completed item is not re-claimed
    Given mails "feature/first@50, feature/second@50" are queued to "coder"
    And "coder" has pulled its mail
    And "coder" completes its mail with result "green"
    When "coder" pulls its mail
    Then the pulled task is "feature/second"

  # Mail recovery 3 - a dispatch after completion is a new item
  Scenario: Mail recovery 3 - a dispatch after completion is a new item
    Given mail is sent from "orchestrator" to "coder" as a handoff for task "feature/periods" with priority "50" and message "start"
    And "coder" has pulled its mail
    And "coder" completes its mail with result "green"
    When that mail is sent again
    Then the send reports "QUEUED"

  # Mail recovery 4 - a corrupt queued item fails closed
  Scenario: Mail recovery 4 - a corrupt queued item fails closed
    Given a corrupt mail item is queued to "coder"
    When "coder" pulls its mail
    Then the pull is refused with a problem naming "corrupt"
    And the corrupt mail item is still queued

  # Mail recovery 5 - a corrupt in-process item fails closed
  Scenario: Mail recovery 5 - a corrupt in-process item fails closed
    Given mails "feature/periods@50" are queued to "coder"
    And "coder" has pulled its mail
    And the in-process mail item is corrupted
    When "coder" completes its mail with result "green"
    Then the completion refusal names "corrupt"
    And the corrupt mail item is still in process
