Feature: Harness CLI

  # The harness CLI resolves the pack wiring and manages the shared areas.
  # `config` prints the resolved wiring as JSON, `status` marks each resolved
  # path present or missing, and `clean` empties a managed area, refusing to
  # discard state while an item is in process unless forced.

  Background:
    Given no harness environment overrides

  # Harness CLI 1 - config prints the resolved wiring as JSON
  Scenario: Harness CLI 1 - config prints the resolved wiring as JSON
    Given a temporary project with all harness roots inside it
    When the harness config command runs
    Then the config output is the resolved wiring as JSON

  # Harness CLI 2 - status marks each resolved row present or missing
  Scenario Outline: Harness CLI 2 - status marks each resolved row present or missing
    Given a temporary project whose configured roots are absent
    When the harness status command runs
    Then the status reports a row for the pack, config, workspace, state, artifacts, and hot
    And the status marks the <row> row as "<marker>"

    Examples:
      | row       | marker |
      | PACK      | ok     |
      | CONFIG    | ok     |
      | WORKSPACE | -      |
      | STATE     | -      |
      | ARTIFACTS | -      |
      | HOT       | -      |

  # Harness CLI 3 - clean state refuses while an item is in process
  Scenario Outline: Harness CLI 3 - clean state refuses while an item is in process
    Given a temporary project with all harness roots inside it
    And an in-process mail item under the project state directory
    When the harness clean command runs for <target>
    Then the harness clean command refuses with exit code <exit_code>
    And the refusal reports the in-process item
    And the project state directory still holds the in-process item

    Examples:
      | target | exit_code |
      | state  | 2         |

  # Harness CLI 4 - clean state force cleans while an item is in process
  Scenario Outline: Harness CLI 4 - clean state force cleans while an item is in process
    Given a temporary project with all harness roots inside it
    And an in-process mail item under the project state directory
    When the harness clean command force-cleans the state area
    Then the harness clean command completes and exits with code <exit_code>
    And the project <target> directory is empty

    Examples:
      | target | exit_code |
      | state  | 0         |

  # Harness CLI 5 - clean empties the named managed area
  Scenario Outline: Harness CLI 5 - clean empties the named managed area
    Given a temporary project with all harness roots inside it
    And a generated file under the project <target> directory
    When the harness clean command runs for <target>
    Then the harness clean command completes and exits with code <exit_code>
    And the project <target> directory is empty

    Examples:
      | target    | exit_code |
      | hot       | 0         |
      | artifacts | 0         |
      | state     | 0         |

  # Harness CLI 6 - clean all empties hot, state, and artifacts
  Scenario Outline: Harness CLI 6 - clean all empties hot, state, and artifacts
    Given a temporary project with all harness roots inside it
    And generated files under the project hot, artifacts, and state directories
    When the harness clean command runs for <target>
    Then the harness clean command completes and exits with code <exit_code>
    And the project hot, artifacts, and state directories are empty

    Examples:
      | target | exit_code |
      | all    | 0         |

  # Harness CLI 7 - clean state refuses while a team task is in process
  # Rationale: the in-process check used the old `team/**/seats/*` glob and
  # missed the live `tasks/` layout, so it now counts team tasks too.
  Scenario Outline: Harness CLI 7 - clean state refuses while a team task is in process
    Given a temporary project with all harness roots inside it
    And the orchestrator opens task "feature/periods" for role "coder"
    When the harness clean command runs for <target>
    Then the harness clean command refuses with exit code <exit_code>
    And the refusal reports the in-process item
    And the project state directory still holds the in-process item

    Examples:
      | target | exit_code |
      | state  | 2         |

  # Harness CLI 8 - clean with no target cleans the hot area
  # Rationale: the documented default clean target is hot, so a bare `clean`
  # must empty the shared hot area.
  Scenario Outline: Harness CLI 8 - clean with no target cleans the hot area
    Given a temporary project with all harness roots inside it
    And a generated file under the project <target> directory
    When the harness clean command runs with no target
    Then the harness clean command completes and exits with code <exit_code>
    And the project <target> directory is empty

    Examples:
      | target | exit_code |
      | hot    | 0         |
