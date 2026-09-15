Feature: Durable store

  # The durable JSON state primitives shared by the harness tools: a UTC stamp,
  # an atomic write, a sorted JSON listing, a monotonic sequence counter, an
  # exclusive advisory lock, and the shared CLI error rendering.

  # Durable store 1 - iso_now returns a UTC stamp in the documented format
  Scenario: Durable store 1 - iso_now returns a UTC stamp in the documented format
    When the durable store stamps the current time
    Then the stamp is a UTC timestamp in the documented format
    And the stamp is close to the current time

  # Durable store 2 - an atomic write round-trips and leaves no temp file
  Scenario: Durable store 2 - an atomic write round-trips and leaves no temp file
    When the durable store atomically writes a document
    Then the written document reads back unchanged
    And the document directory holds no temporary file

  # Durable store 3 - list_json returns sorted non-dot JSON files
  Scenario Outline: Durable store 3 - list_json returns sorted non-dot JSON files
    Given the durable store directory holds the files "<files>"
    When the durable store lists the directory
    Then the listing is "<listing>"

    Examples:
      | files                            | listing       |
      | b.json,a.json                    | a.json,b.json |
      | z.json,m.txt,.hidden.json,a.json | a.json,z.json |

  # Durable store 4 - next_seq increments a monotonic counter
  Scenario Outline: Durable store 4 - next_seq increments a monotonic counter
    Given the durable store counter starts at <start>
    When the durable store allocates <calls> sequence numbers
    Then the allocated sequence numbers are "<sequence>"

    Examples:
      | start | calls | sequence |
      | 0     | 3     | 1,2,3    |
      | 4     | 2     | 5,6      |
      | 9     | 1     | 10       |

  # Durable store 5 - the lock excludes a second holder
  Scenario Outline: Durable store 5 - the lock excludes a second holder
    When a second holder requests the lock "<requested>" while the store holds the lock "<held>"
    Then the second holder <outcome>

    Examples:
      | held    | requested | outcome    |
      | mailbox | mailbox   | is blocked |
      | mailbox | journal   | is admitted |

  # Durable store 6 - run_cli renders tool errors as exit 2
  Scenario Outline: Durable store 6 - run_cli renders tool errors as exit 2
    When the durable store CLI refuses with the problems "<problems>"
    Then the durable store CLI exits with code <exit_code>
    And the durable store CLI prints the problem lines "<lines>"

    Examples:
      | problems                     | exit_code | lines                            |
      | first problem                | 2         | - first problem                  |
      | first problem;second problem | 2         | - first problem;- second problem |
