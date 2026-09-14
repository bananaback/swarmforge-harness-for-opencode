Feature: Harness wiring

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

  # Harness wiring 4 - the environment overrides the config
  Scenario: Harness wiring 4 - the environment overrides the config
    Given a temporary project with its own harness config
    When the environment sets the state root to an override directory
    Then loading wiring reports the override directory as the state root

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
