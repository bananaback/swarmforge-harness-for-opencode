Feature: Mail queue

  # A durable mail item is queued once for each recipient role, claimed by one
  # session at a time, resumed before new mail, completed once, and reported by
  # status. Queue state is owned by the tool; nothing is repaired by hand.

  Background:
    Given a temporary project with its own state root

  # Mail queue 1 - a handoff is queued to every named recipient
  Scenario Outline: Mail queue 1 - a handoff is queued to every named recipient
    When mail is sent from "<from>" to "<to>" as a handoff for task "<task>" with priority "<priority>" and message "<message>"
    Then the send reports "QUEUED"
    And the send reports the recipients "<recipients>"
    And the "coder" mailbox queued count is "1"
    And the "refactorer" mailbox queued count is "1"

    Examples:
      | from         | to               | task            | priority | message | recipients        |
      | orchestrator | coder,refactorer | feature/periods | 50       | start   | coder, refactorer |

  # Mail queue 2 - a handoff payload names the task and carries the message
  Scenario Outline: Mail queue 2 - a handoff payload names the task and carries the message
    Given mail is sent from "<from>" to "<to>" as a handoff for task "<task>" with priority "<priority>" and message "<message>"
    When "coder" pulls its mail
    Then the pulled payload names task "<task>"
    And the pulled payload carries "<message>"

    Examples:
      | from         | to    | task            | priority | message        |
      | orchestrator | coder | feature/periods | 50       | start the work |

  # Mail queue 3 - a note payload is the message alone
  Scenario: Mail queue 3 - a note payload is the message alone
    Given mail is sent from "orchestrator" to "coder" as a note with message "heads up"
    When "coder" pulls its mail
    Then the pulled payload is "heads up"

  # Mail queue 4 - an identical live message is not queued twice
  Scenario Outline: Mail queue 4 - an identical live message is not queued twice
    Given mail is sent from "<from>" to "<to>" as a handoff for task "<task>" with priority "<priority>" and message "<message>"
    When that mail is sent again
    Then the send reports "DUPLICATE: coder"
    And the "coder" mailbox queued count is "1"

    Examples:
      | from         | to    | task            | priority | message |
      | orchestrator | coder | feature/periods | 50       | start   |

  # Mail queue 5 - pull claims the highest-priority queued item
  Scenario Outline: Mail queue 5 - pull claims the highest-priority queued item
    Given mails "<mails>" are queued to "coder"
    When "coder" pulls its mail
    Then the pulled task is "<task>"
    And the pulled priority is "<priority>"

    Examples:
      | mails                              | task           | priority |
      | feature/slow@90, feature/urgent@10 | feature/urgent | 10       |
      | bug/minor@80, bug/critical@20      | bug/critical   | 20       |

  # Mail queue 6 - pull resumes an in-process item before claiming new mail
  Scenario Outline: Mail queue 6 - pull resumes an in-process item before claiming new mail
    Given mails "<mails>" are queued to "coder"
    And "coder" has pulled its mail
    And mail is sent from "<from>" to "<to>" as a handoff for task "<task>" with priority "<priority>" and message "<message>"
    When "coder" pulls its mail
    Then the pull reports "RESUMED: yes"
    And the pulled task is "feature/first"

    Examples:
      | mails            | from         | to    | task           | priority | message |
      | feature/first@50 | orchestrator | coder | feature/second | 50       | two     |

  # Mail queue 7 - batch pull claims all top-priority queued items as one unit
  Scenario Outline: Mail queue 7 - batch pull claims all top-priority queued items as one unit
    Given mails "<mails>" are queued to "coder"
    When "coder" pulls its mail in batch mode
    Then the pull reports a batch of "<count>" items
    And the batch priority is "<priority>"
    And the "coder" mailbox in-process count is "<count>"

    Examples:
      | mails                                          | count | priority |
      | feature/alpha@20, feature/beta@20, feature/gamma@80 | 2     | 20       |

  # Mail queue 8 - done completes the in-process item and reports no further mail
  Scenario Outline: Mail queue 8 - done completes the in-process item and reports no further mail
    Given mails "<mails>" are queued to "coder"
    And "coder" has pulled its mail
    When "coder" completes its mail with result "<result>"
    Then the completion reports "NO_TASK"
    And the "coder" mailbox completed count is "1"
    And the completed item records result "<result>"

    Examples:
      | mails            | result |
      | feature/periods@50 | green  |

  # Mail queue 9 - done reports waiting mail when more is queued
  Scenario Outline: Mail queue 9 - done reports waiting mail when more is queued
    Given mails "<mails>" are queued to "coder"
    And "coder" has pulled its mail
    And mail is sent from "<from>" to "<to>" as a handoff for task "<task>" with priority "<priority>" and message "<message>"
    When "coder" completes its mail with result "<result>"
    Then the completion reports "MAIL_WAITING"

    Examples:
      | mails            | from         | to    | task           | priority | message | result |
      | feature/first@50 | orchestrator | coder | feature/second | 50       | two     | green  |

  # Mail queue 10 - status reports queued and in-process counts
  Scenario Outline: Mail queue 10 - status reports queued and in-process counts
    Given mails "<mails>" are queued to "coder"
    And "coder" has pulled its mail
    When mail status is read for "coder"
    Then the status queued count is "1"
    And the status in-process count is "1"

    Examples:
      | mails                              |
      | feature/first@50, feature/second@50 |

  # Mail queue 11 - status reports every known role
  Scenario: Mail queue 11 - status reports every known role
    When mail status is read for all roles
    Then the status names role "coder"
    And the status names role "mentor"

  # Mail queue 12 - a foreign session cannot resume a claimed item
  Scenario Outline: Mail queue 12 - a foreign session cannot resume a claimed item
    Given mails "<mails>" are queued to "coder"
    And "coder" has pulled its mail as session "<owner>"
    When "coder" pulls its mail as session "<other>"
    Then the pull is refused with a problem naming "owned by session <owner>"

    Examples:
      | mails            | owner     | other     |
      | feature/periods@50 | session-a | session-b |

  # Mail queue 13 - takeover lets another session resume the item
  Scenario Outline: Mail queue 13 - takeover lets another session resume the item
    Given mails "<mails>" are queued to "coder"
    And "coder" has pulled its mail as session "<owner>"
    When "coder" takes over its mail as session "<other>"
    Then the pull reports "RESUMED: yes"
    And the "coder" in-process owner is "<other>"

    Examples:
      | mails            | owner     | other     |
      | feature/periods@50 | session-a | session-b |

  # Mail queue 14 - a task pull is ambiguous after a batch claim
  Scenario Outline: Mail queue 14 - a task pull is ambiguous after a batch claim
    Given mails "<mails>" are queued to "coder"
    And "coder" has pulled its mail in batch mode
    When "coder" pulls its mail
    Then the pull is refused with a problem naming "more than one in-process item"

    Examples:
      | mails                          |
      | feature/alpha@20, feature/beta@20 |
