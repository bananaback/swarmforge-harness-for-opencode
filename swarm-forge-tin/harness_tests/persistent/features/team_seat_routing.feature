Feature: Team seat routing

  # Work is routed by (task, seat). A session is bound to exactly one seat; the
  # binding is atomic and resets that seat's delivery state. Pull resolves a
  # bound session, and status reports every seat's session, load, and cursor.

  Background:
    Given a temporary project with its own state root
    And the orchestrator opens task "feature/periods" for role "coder"

  # Team seat routing 1 - a fresh session binds to a seat
  Scenario Outline: Team seat routing 1 - a fresh session binds to a seat
    When session "<session>" binds to seat "<seat>" of task "<task>"
    Then the bind reports "BOUND"
    And the status shows seat "<seat>" held by session "<session>"

    Examples:
      | session  | seat   | task            |
      | worker-1 | worker | feature/periods |
      | mentor-1 | mentor | feature/periods |

  # Team seat routing 2 - takeover rebinds a seat and resets its delivery state
  Scenario Outline: Team seat routing 2 - takeover rebinds a seat and resets its delivery state
    Given session "<holder>" is bound to seat "<other>" of task "<task>"
    And the worker loads its context
    When session "<session>" takes over seat "<seat>" of task "<task>"
    Then the bind reports "REBOUND"
    And the status shows seat "<seat>" held by session "<session>"
    And the status shows seat "<seat>" loaded "no" with cursor "0"

    Examples:
      | holder   | other  | session  | seat   | task            |
      | worker-1 | worker | worker-2 | worker | feature/periods |

  # Team seat routing 3 - a bound seat refuses another session
  Scenario Outline: Team seat routing 3 - a bound seat refuses another session
    Given session "<holder>" is bound to seat "<other>" of task "<task>"
    When session "<session>" binds to seat "<seat>" of task "<task>"
    Then the bind refusal names "<problem>"

    Examples:
      | holder   | other  | session  | seat   | task            | problem                                      |
      | worker-1 | worker | worker-2 | worker | feature/periods | seat `worker` is already bound to session worker-1 |

  # Team seat routing 4 - a session serves exactly one seat
  Scenario Outline: Team seat routing 4 - a session serves exactly one seat
    Given session "<holder>" is bound to seat "<other>" of task "<task>"
    When session "<session>" binds to seat "<seat>" of task "<task>"
    Then the bind refusal names "<problem>"

    Examples:
      | holder   | other  | session  | seat   | task            | problem                                              |
      | worker-1 | worker | worker-1 | mentor | feature/periods | session worker-1 is already bound to feature/periods/worker |

  # Team seat routing 5 - pull resumes a bound session
  Scenario Outline: Team seat routing 5 - pull resumes a bound session
    Given session "<holder>" is bound to seat "<other>" of task "<task>"
    When session "<session>" pulls its chunk
    Then the pull reports "RESUMED: yes"

    Examples:
      | holder   | other  | session  | task            |
      | worker-1 | worker | worker-1 | feature/periods |

  # Team seat routing 6 - an unbound session cannot pull
  Scenario Outline: Team seat routing 6 - an unbound session cannot pull
    When session "<session>" pulls its chunk
    Then the pull refusal names "<problem>"

    Examples:
      | session | problem                                    |
      | ghost   | session is not bound to any team seat      |

  # Team seat routing 7 - a seat hint must match the bound seat
  Scenario Outline: Team seat routing 7 - a seat hint must match the bound seat
    Given session "<holder>" is bound to seat "<other>" of task "<task>"
    When session "<session>" pulls its chunk for the "<seat>" seat
    Then the pull refusal names "<problem>"

    Examples:
      | holder   | other  | session  | seat   | task            | problem                                |
      | worker-1 | worker | worker-1 | mentor | feature/periods | session is bound to `worker`, not `mentor` |

  # Team seat routing 8 - status reports a loaded seat
  Scenario Outline: Team seat routing 8 - status reports a loaded seat
    Given session "<holder>" is bound to seat "<other>" of task "<task>"
    And the worker loads its context
    When status is read
    Then the status shows seat "<seat>" held by session "<session>"
    And the status shows seat "<seat>" loaded "yes" with cursor "2"

    Examples:
      | holder   | other  | session  | seat   | task            |
      | worker-1 | worker | worker-1 | worker | feature/periods |

  # Team seat routing 9 - status reports an unloaded seat
  Scenario Outline: Team seat routing 9 - status reports an unloaded seat
    Given session "<holder>" is bound to seat "<other>" of task "<task>"
    When status is read
    Then the status shows seat "<seat>" held by session "<session>"
    And the status shows seat "<seat>" loaded "no" with cursor "0"

    Examples:
      | holder   | other  | session  | seat   | task            |
      | mentor-1 | mentor | mentor-1 | mentor | feature/periods |

  # Team seat routing 10 - status --ready lists spawnable seats
  Scenario Outline: Team seat routing 10 - status --ready lists spawnable seats
    When the ready list is read
    Then the ready list shows "<line>"

    Examples:
      | line                                       |
      | READY: feature/periods worker SPAWN_PENDING |
      | READY: feature/periods mentor SPAWN_PENDING |

  # Team seat routing 11 - a bound seat is queued in the ready list
  Scenario Outline: Team seat routing 11 - a bound seat is queued in the ready list
    Given session "<holder>" is bound to seat "<other>" of task "<task>"
    When the ready list is read
    Then the ready list shows "<line>"

    Examples:
      | holder   | other  | task            | line                                 |
      | worker-1 | worker | feature/periods | READY: feature/periods worker queued |
