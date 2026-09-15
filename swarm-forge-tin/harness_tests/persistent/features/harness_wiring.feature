Feature: Harness wiring

  # Wiring resolves the pack, workspace, state, artifacts, hot, and persistent
  # roots from the nearest `harness.json`, then from the documented defaults,
  # then from the `SWARM_*` environment overrides. The configured `kind`
  # selects the persistent root a workspace runs its tests from.

  Background:
    Given no harness environment overrides

  # Harness wiring 1 - the harness points at itself
  Scenario: Harness wiring 1 - the harness points at itself
    Given the harness pack
    When wiring is loaded from the pack
    Then the resolved workspace is the pack parent
    And the configured source roots contain the pack tools directory
    And the harness persistent root is the pack harness tests directory
    And the shared hot area is the pack hot tests directory

  # Harness wiring 2 - a project config points at that project
  Scenario: Harness wiring 2 - a project config points at that project
    Given a temporary project with its own harness config
    When wiring is loaded from that project
    Then the resolved workspace is that project
    And the resolved hot area is that project hot directory
    And the resolved state root is that project state directory
    And the project persistent root is the project tests directory

  # Harness wiring 3 - the nearest config wins
  Scenario: Harness wiring 3 - the nearest config wins
    Given a temporary project with its own harness config
    And the pack config sets a different workspace
    When wiring is loaded from that project
    Then the resolved workspace is that project

  # Harness wiring 4 - the environment overrides the state root
  Scenario Outline: Harness wiring 4 - the environment overrides the state root
    Given a temporary project with its own harness config
    When the environment sets the <variable> to an override directory
    Then loading wiring reports the override directory as the state root

    Examples:
      | variable         |
      | SWARM_STATE_ROOT |

  # Harness wiring 5 - cleaning the shared hot area leaves persistent tests
  Scenario: Harness wiring 5 - cleaning the shared hot area leaves persistent tests
    Given a temporary project with its own harness config
    And a generated file under the project hot directory
    When the harness clean command runs for hot
    Then the project hot directory is empty
    And the project persistent root still exists

  # Harness wiring 6 - an invalid config is rejected
  Scenario: Harness wiring 6 - an invalid config is rejected
    Given a temporary project with a malformed harness config
    When wiring is requested from that project
    Then loading fails with a wiring error

  # Harness wiring 7 - a missing config file is an error
  Scenario: Harness wiring 7 - a missing config file is an error
    Given a temporary project with its own harness config
    And the environment points the config at a missing file
    When wiring is requested from that project
    Then loading fails with a wiring error

  # Harness wiring 8 - the environment selects the pack config
  Scenario: Harness wiring 8 - the environment selects the pack config
    Given a temporary directory with no harness config
    And the environment selects the harness pack
    When wiring is loaded from that directory
    Then the resolved workspace is the pack parent

  # Harness wiring 9 - absent fields fall back to defaults
  Scenario: Harness wiring 9 - absent fields fall back to defaults
    Given a temporary project with a config that sets no roots
    When wiring is loaded from that project
    Then the resolved workspace is the pack parent
    And the resolved artifacts root is the pack dump directory
    And the shared hot area is the pack hot tests directory
    And the configured roles are the default roles

  # Harness wiring 10 - the environment overrides the workspace
  Scenario Outline: Harness wiring 10 - the environment overrides the workspace
    Given a temporary project with its own harness config
    When the environment sets the <variable> to an override directory
    Then the resolved workspace root is the override directory

    Examples:
      | variable        |
      | SWARM_WORKSPACE |

  # Harness wiring 11 - the environment overrides the hot area
  Scenario Outline: Harness wiring 11 - the environment overrides the hot area
    Given a temporary project with its own harness config
    When the environment sets the <variable> to an override directory
    Then the resolved hot area is the override directory

    Examples:
      | variable  |
      | SWARM_HOT |

  # Harness wiring 12 - a self-hosted pack selects the harness-kind root
  Scenario Outline: Harness wiring 12 - a self-hosted pack selects the harness-kind root
    Given a temporary self-hosted pack whose persistent roots are a project root then a harness root
    When wiring is loaded from the self-hosted pack
    And the persistent test root is selected
    Then the selected persistent root has kind "<kind>"

    Examples:
      | kind    |
      | harness |

  # Harness wiring 13 - a wired project selects the project-kind root
  Scenario Outline: Harness wiring 13 - a wired project selects the project-kind root
    Given a temporary wired project whose persistent roots are a harness root then a project root
    When wiring is loaded from that project
    And the persistent test root is selected
    Then the selected persistent root has kind "<kind>"

    Examples:
      | kind    |
      | project |
