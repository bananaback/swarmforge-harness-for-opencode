Feature: Mail send validation

  # Every send is validated before any mail is queued. A refused send exits with
  # code 2 and reports one problem line per problem; the queue is unchanged.

  Background:
    Given a temporary project with its own state root

  # Mail send validation 1 - a refused send reports its full problem set
  Scenario Outline: Mail send validation 1 - a refused send reports its full problem set
    When mail is sent from "<from>" to "<to>" as a handoff for task "<task>" with priority "<priority>" and message "start"
    Then the send is refused with the problems "<problems>"
    And no mail is queued for "coder"

    Examples:
      | from         | to                 | priority | task            | problems |
      | Orchestrator | Coder              | 5        | /leading        | sender must be a lowercase role name; recipient `Coder` must be a lowercase role name; `priority` must be two digits from 00 to 99; `task` segments must start alphanumeric |
      | orchestrator | coder,mentor,coder | 50       | feature/periods | `to` must not repeat a recipient |
      | nobody       | coder              | 50       | feature/periods | unknown sender `nobody` |
      | orchestrator | nobody             | 50       | feature/periods | unknown recipient `nobody` |
      | orchestrator | coder              | 100      | feature/periods | `priority` must be two digits from 00 to 99 |
      | orchestrator | coder              | 50       | feature/!bad     | `task` segments must start alphanumeric |
      | orchestrator | coder              | 50       | trailing/       | `task` segments must start alphanumeric |

  # Mail send validation 2 - a handoff without a task is refused
  Scenario Outline: Mail send validation 2 - a handoff without a task is refused
    When a handoff without a task is sent
    Then the send is refused with the problems "<problems>"
    And no mail is queued for "coder"

    Examples:
      | problems                         |
      | `handoff` requires a `task` name |

  # Mail send validation 3 - an over-long task name is refused
  Scenario Outline: Mail send validation 3 - an over-long task name is refused
    When a handoff with an over-long task is sent
    Then the send is refused with the problems "<problems>"
    And no mail is queued for "coder"

    Examples:
      | problems                             |
      | `task` must be at most 80 characters |

  # Mail send validation 4 - a note without a message is refused
  Scenario Outline: Mail send validation 4 - a note without a message is refused
    When a note without a message is sent
    Then the send is refused with the problems "<problems>"
    And no mail is queued for "coder"

    Examples:
      | problems                   |
      | `note` requires a `message` |

  # Mail send validation 5 - an over-long note message is refused
  Scenario Outline: Mail send validation 5 - an over-long note message is refused
    When a note with an over-long message is sent
    Then the send is refused with the problems "<problems>"
    And no mail is queued for "coder"

    Examples:
      | problems                                     |
      | `note` message must be at most 80 characters |

  # Mail send validation 6 - an over-long handoff message is refused
  Scenario Outline: Mail send validation 6 - an over-long handoff message is refused
    When a handoff with an over-long message is sent
    Then the send is refused with the problems "<problems>"
    And no mail is queued for "coder"

    Examples:
      | problems                                        |
      | `handoff` message must be at most 300 characters |

  # Mail send validation 7 - a multi-line message is refused
  Scenario Outline: Mail send validation 7 - a multi-line message is refused
    When a handoff with a multi-line message is sent
    Then the send is refused with the problems "<problems>"
    And no mail is queued for "coder"

    Examples:
      | problems                   |
      | `message` must be one line |

  # Mail send validation 8 - a builtin sender is accepted
  Scenario: Mail send validation 8 - a builtin sender is accepted
    When a handoff is sent from the builtin sender
    Then the send reports "QUEUED"
