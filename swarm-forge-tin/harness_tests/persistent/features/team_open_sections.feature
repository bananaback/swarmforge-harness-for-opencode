Feature: Team open sections

  # team open seeds a task's fields from the orchestrator's flags first, then
  # from the brief and design text. The brief carries TASK, DEFINITION OF DONE,
  # and the mentor fields; the design carries INTERFACE CONTRACT and FILES. A
  # heading may be a markdown heading, a bold line, or a plain uppercase line.

  Background:
    Given a temporary project with its own state root

  # Team open sections 1 - the brief supplies TASK and DEFINITION OF DONE
  Scenario Outline: Team open sections 1 - the brief supplies TASK and DEFINITION OF DONE
    Given a brief whose TASK section reads "Implement strict parsing"
    And the brief also defines DEFINITION OF DONE as "tests pass"
    When the orchestrator opens task "c1" for role "<role>" with the given inputs
    Then the opened task text is "Implement strict parsing"
    And the opened definition of done is "tests pass"

    Examples:
      | role  |
      | coder |

  # Team open sections 2 - the design supplies INTERFACE CONTRACT and FILES
  Scenario Outline: Team open sections 2 - the design supplies INTERFACE CONTRACT and FILES
    Given a design whose INTERFACE CONTRACT section reads "frozen signature"
    And the design also defines FILES as "src/a.py"
    When the orchestrator opens task "c1" for role "<role>" with the given inputs
    Then the opened interface contract is "frozen signature"
    And the opened files field is "src/a.py"

    Examples:
      | role  |
      | coder |

  # Team open sections 3 - the brief supplies the mentor fields
  Scenario Outline: Team open sections 3 - the brief supplies the mentor fields
    Given a brief with a "<section>" section reading "<value>"
    When the orchestrator opens task "c1" for role "<role>" with the given inputs
    Then the opened mentor field "<section>" is "<value>"

    Examples:
      | role   | section | value                            |
      | mentor | GOAL    | fix the failing tests            |
      | mentor | RULES   | never edit the feature file      |
      | mentor | ASK     | why does the parser reject this? |
      | mentor | FAILURE | AssertionError: expected 3 got 2 |

  # Team open sections 4 - explicit flags win over the text
  Scenario Outline: Team open sections 4 - explicit flags win over the text
    Given a brief whose TASK section reads "from the brief"
    And the brief also defines DEFINITION OF DONE as "from the brief"
    And a design whose INTERFACE CONTRACT section reads "from the design"
    And the design also defines FILES as "from the design"
    When the orchestrator opens task "c1" for role "<role>" with explicit flags
    Then the opened task text is "explicit text"
    And the opened definition of done is "explicit done"
    And the opened interface contract is "explicit contract"
    And the opened files field is "explicit files"
    And the opened mentor field "GOAL" is "explicit goal"

    Examples:
      | role  |
      | coder |

  # Team open sections 5 - a heading may be markdown, bold, or plain
  Scenario Outline: Team open sections 5 - a heading may be markdown, bold, or plain
    Given a brief with a "<style>" TASK heading reading "Implement strict parsing"
    When the orchestrator opens task "c1" for role "<role>" with the given inputs
    Then the opened task text is "Implement strict parsing"

    Examples:
      | role  | style    |
      | coder | markdown |
      | coder | bold     |
      | coder | plain    |

  # Team open sections 6 - a brief with no section headings leaves the fields empty
  Scenario Outline: Team open sections 6 - a brief with no section headings leaves the fields empty
    Given a brief with no section headings
    When the orchestrator opens task "c1" for role "<role>" with the given inputs
    Then the opened task text and definition of done are empty

    Examples:
      | role  |
      | coder |
