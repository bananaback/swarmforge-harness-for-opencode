Feature: Acceptance pipeline

  # The spec path: a feature parses to the canonical JSON IR, the IR dry-checks
  # for repeated wording, the generator emits one test per example, and the
  # mutator proves an example value reaches the suite.

  # Acceptance pipeline 1 - the parser emits the documented JSON IR
  Scenario Outline: Acceptance pipeline 1 - the parser emits the documented JSON IR
    Given a feature file named "<name>" with a scenario "<scenario>" and the step "<step>"
    When the acceptance parser parses it
    Then the parsed feature is named "<name>"
    And the parsed scenario is named "<scenario>"
    And the parsed step is "<step>" with parameter "<parameter>"

    Examples:
      | name  | scenario     | step               | parameter |
      | Login | Login works  | the user is <user> | user      |
      | Cart  | Cart empties | the cart has <n>   | n         |

  # Acceptance pipeline 2 - a file with no feature declaration is rejected
  Scenario Outline: Acceptance pipeline 2 - a file with no feature declaration is rejected
    Given a feature file that declares no feature and contains "<line>"
    When the acceptance parser parses it
    Then the acceptance parser exits with code <exit_code>

    Examples:
      | line             | exit_code |
      | Scenario: orphan | 1         |

  # Acceptance pipeline 3 - examples outside a scenario are rejected
  Scenario Outline: Acceptance pipeline 3 - examples outside a scenario are rejected
    Given a feature file with an examples table outside any scenario
    When the acceptance parser parses it
    Then the acceptance parser exits with code <exit_code>

    Examples:
      | exit_code |
      | 1         |

  # Acceptance pipeline 4 - a ragged example row is rejected
  Scenario Outline: Acceptance pipeline 4 - a ragged example row is rejected
    Given a feature file whose example row has <row_cells> cells and whose header has <header_cells> cells
    When the acceptance parser parses it
    Then the acceptance parser exits with code <exit_code>

    Examples:
      | row_cells | header_cells | exit_code |
      | 1         | 2            | 1         |
      | 3         | 2            | 1         |

  # Acceptance pipeline 5 - a duplicate step in one scenario is reported by default
  Scenario Outline: Acceptance pipeline 5 - a duplicate step in one scenario is reported by default
    Given a parsed IR that repeats the step "<step>" in <scenarios> scenarios
    When the dry checker runs by default
    Then the dry report <outcome> a "<kind>" finding

    Examples:
      | step          | scenarios | outcome | kind                  |
      | the same step | 1         | reports | duplicate-in-scenario |

  # Acceptance pipeline 6 - an exact duplicate across scenarios needs --include-exact
  Scenario Outline: Acceptance pipeline 6 - an exact duplicate across scenarios needs --include-exact
    Given a parsed IR that repeats the step "<step>" in <scenarios> scenarios
    When the dry checker runs <mode>
    Then the dry report contains only the "<kinds>" kinds

    Examples:
      | step          | scenarios | mode                 | kinds                                  |
      | the same step | 2         | by default           | duplicate-in-scenario                  |
      | the same step | 2         | with --include-exact | duplicate-in-scenario, exact-duplicate |

  # Acceptance pipeline 7 - placeholder variants are reported
  Scenario Outline: Acceptance pipeline 7 - placeholder variants are reported
    Given a parsed IR whose scenario holds the steps "<first>" and "<second>"
    When the dry checker runs by default
    Then the dry report <outcome> a "<kind>" finding

    Examples:
      | first                     | second                 | outcome | kind                |
      | the room is <destination> | the room is <expected> | reports | placeholder-variant |

  # Acceptance pipeline 8 - the generator emits one test per example
  Scenario Outline: Acceptance pipeline 8 - the generator emits one test per example
    Given a parsed IR whose scenario has <examples> example rows
    When the acceptance generator generates entry points
    Then the generated entry point declares <tests> test functions

    Examples:
      | examples | tests |
      | 3        | 3     |
      | 1        | 1     |

  # Acceptance pipeline 9 - the mutator changes an example value and the suite catches it
  Scenario Outline: Acceptance pipeline 9 - the mutator changes an example value and the suite catches it
    Given a tiny feature whose single example value is asserted
    When the mutator runs at level "<level>"
    Then the mutation report has <killed> killed and <survived> surviving mutants

    Examples:
      | level | killed | survived |
      | hard  | 1      | 0        |
