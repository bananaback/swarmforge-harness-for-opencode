# Token usage calculation.
#
# A sessions value encodes one or more sessions separated by ';'.
# Each session is:
#   input,output,reasoning,cache_read,cache_write,cost,requests
# An empty sessions value means no sessions.

Feature: Token Usage

  Scenario Outline: Token Usage 1 - total input is input plus cache read
    Given a session with input <input>, output <output>, reasoning <reasoning>, cache read <cache_read>, cache write <cache_write>, and cost <cost>
    When the session's token usage is calculated
    Then the total input is <total_input>

    Examples:
      | input | output | reasoning | cache_read | cache_write | cost  | total_input |
      | 1000  | 200    | 50        | 400        | 10          | 0.25  | 1400        |
      | 3000  | 100    | 25        | 0          | 5           | 0.5   | 3000        |
      | 0     | 500    | 75        | 250        | 0           | 0.125 | 250         |

  Scenario Outline: Token Usage 2 - total output is output plus reasoning
    Given a session with input <input>, output <output>, reasoning <reasoning>, cache read <cache_read>, cache write <cache_write>, and cost <cost>
    When the session's token usage is calculated
    Then the total output is <total_output>

    Examples:
      | input | output | reasoning | cache_read | cache_write | cost  | total_output |
      | 1000  | 200    | 50        | 400        | 10          | 0.25  | 250          |
      | 3000  | 100    | 25        | 0          | 5           | 0.5   | 125          |
      | 0     | 500    | 75        | 250        | 0           | 0.125 | 575          |

  Scenario Outline: Token Usage 3 - cache hit ratio is cache read over total input
    Given a session with input <input>, output <output>, reasoning <reasoning>, cache read <cache_read>, cache write <cache_write>, and cost <cost>
    When the session's token usage is calculated
    Then the cache hit ratio is <cache_hit> rounded to 6 decimal places

    Examples:
      | input | output | reasoning | cache_read | cache_write | cost  | cache_hit |
      | 1000  | 200    | 50        | 0          | 10          | 0.25  | 0         |
      | 750   | 100    | 25        | 250        | 5           | 0.5   | 0.25      |
      | 0     | 500    | 75        | 1000       | 0           | 0.125 | 1         |
      | 0     | 200    | 50        | 0          | 0           | 0     | 0         |

  Scenario Outline: Token Usage 4 - output ratio is total output over total input
    Given a session with input <input>, output <output>, reasoning <reasoning>, cache read <cache_read>, cache write <cache_write>, and cost <cost>
    When the session's token usage is calculated
    Then the output ratio is <output_ratio> rounded to 6 decimal places

    Examples:
      | input | output | reasoning | cache_read | cache_write | cost  | output_ratio |
      | 1000  | 200    | 50        | 0          | 10          | 0.25  | 0.25         |
      | 500   | 400    | 100       | 500        | 5           | 0.5   | 0.5          |
      | 0     | 0      | 0         | 1000       | 0           | 0.125 | 0            |
      | 0     | 200    | 50        | 0          | 0           | 0     | 0            |

  Scenario Outline: Token Usage 5 - cost is reported unchanged
    Given a session with input <input>, output <output>, reasoning <reasoning>, cache read <cache_read>, cache write <cache_write>, and cost <cost>
    When the session's token usage is calculated
    Then the cost is <cost>

    Examples:
      | input | output | reasoning | cache_read | cache_write | cost  |
      | 1000  | 200    | 50        | 400        | 10          | 0.25  |
      | 3000  | 100    | 25        | 0          | 5           | 0.5   |
      | 0     | 500    | 75        | 250        | 0           | 0.125 |

  Scenario Outline: Token Usage 6 - summary counts sessions
    Given the sessions <sessions>
    When the sessions are summarized
    Then the session count is <session_count>

    Examples:
      | sessions | session_count |
      | 1000,200,50,400,10,0.25,3 | 1 |
      | 1000,200,50,400,10,0.25,3;2000,100,0,0,0,0.5,5 | 2 |
      | | 0 |

  Scenario Outline: Token Usage 7 - summary counts requests
    Given the sessions <sessions>
    When the sessions are summarized
    Then the request count is <request_count>

    Examples:
      | sessions | request_count |
      | 1000,200,50,400,10,0.25,3 | 3 |
      | 1000,200,50,400,10,0.25,3;2000,100,0,0,0,0.5,5 | 8 |
      | | 0 |

  Scenario Outline: Token Usage 8 - summary total input sums inputs and cache reads
    Given the sessions <sessions>
    When the sessions are summarized
    Then the total input is <total_input>

    Examples:
      | sessions | total_input |
      | 1000,200,50,400,10,0.25,3 | 1400 |
      | 1000,200,50,400,10,0.25,3;2000,100,0,0,0,0.5,5 | 3400 |
      | | 0 |

  Scenario Outline: Token Usage 9 - summary total output sums outputs and reasonings
    Given the sessions <sessions>
    When the sessions are summarized
    Then the total output is <total_output>

    Examples:
      | sessions | total_output |
      | 1000,200,50,400,10,0.25,3 | 250 |
      | 1000,200,50,400,10,0.25,3;2000,100,0,0,0,0.5,5 | 350 |
      | | 0 |

  Scenario Outline: Token Usage 10 - summary cache hit ratio is cache reads over total input
    Given the sessions <sessions>
    When the sessions are summarized
    Then the cache hit ratio is <cache_hit> rounded to 6 decimal places

    Examples:
      | sessions | cache_hit |
      | 1000,200,50,400,10,0.25,3 | 0.285714 |
      | 1000,200,50,400,10,0.25,3;2000,100,0,0,0,0.5,5 | 0.117647 |
      | 1000,200,50,0,0,0.25,3;1000,100,0,1000,0,0.5,5 | 0.333333 |
      | | 0 |

  Scenario Outline: Token Usage 11 - summary output ratio is total output over total input
    Given the sessions <sessions>
    When the sessions are summarized
    Then the output ratio is <output_ratio> rounded to 6 decimal places

    Examples:
      | sessions | output_ratio |
      | 1000,200,50,400,10,0.25,3 | 0.178571 |
      | 1000,200,50,400,10,0.25,3;2000,100,0,0,0,0.5,5 | 0.102941 |
      | 1000,0,0,0,0,0.25,3;1000,500,500,1000,0,0.5,5 | 0.333333 |
      | | 0 |

  Scenario Outline: Token Usage 12 - summary cost is the sum of session costs
    Given the sessions <sessions>
    When the sessions are summarized
    Then the cost is <cost>

    Examples:
      | sessions | cost |
      | 1000,200,50,400,10,0.25,3 | 0.25 |
      | 1000,200,50,400,10,0.25,3;2000,100,0,0,0,0.5,5 | 0.75 |
      | | 0 |
