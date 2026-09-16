Feature: Harness portability

  # The pack runs against a committed sample project through a pack-side config.
  # That config is the single source of resolution: switching configs switches
  # the workspace and the persistent test root, the shared areas stay in the
  # pack, and the sample tree is never written to.

  Background:
    Given no harness environment overrides

  # Harness portability 1 - switching configs switches the workspace
  Scenario Outline: Harness portability 1 - switching configs switches the workspace
    Given the harness pack holds its own config and the todo config
    When wiring is loaded through the <config> config
    Then the resolved workspace is the <workspace>

    Examples:
      | config | workspace   |
      | pack   | pack parent |
      | todo   | todo sample |

  # Harness portability 2 - the config chooses where the persistent tests live
  Scenario Outline: Harness portability 2 - the config chooses where the persistent tests live
    Given a temporary project whose config places its persistent root in the <location>
    When the wired config is loaded
    And the persistent test root is selected
    Then the selected persistent root is inside the <location>

    Examples:
      | location |
      | project  |
      | pack     |

  # Harness portability 3 - the shared areas stay in the pack
  Scenario Outline: Harness portability 3 - the shared areas stay in the pack
    Given the todo sample wired through the pack todo config
    When the todo config is resolved
    Then the resolved <area> path is inside the harness pack

    Examples:
      | area      |
      | artifacts |
      | hot       |
      | state     |

  # Harness portability 4 - the sample feature runs end to end
  Scenario: Harness portability 4 - the sample feature runs end to end
    Given the todo sample wired through the pack todo config
    When the todo sample acceptance pipeline runs
    Then the todo sample acceptance pipeline passes

  # Harness portability 5 - the sample tree is never written to
  Scenario: Harness portability 5 - the sample tree is never written to
    Given the todo sample wired through the pack todo config
    And the todo sample is snapshotted
    When the todo sample acceptance pipeline runs
    Then no file appears or changes under the todo sample
