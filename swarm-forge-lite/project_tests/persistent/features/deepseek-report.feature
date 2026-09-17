# DeepSeek per-request report.
#
# A requests value encodes one or more requests separated by ';'.
# Each request is:
#   timestamp,provider,model,input,output,reasoning,cache_read,cache_write,stored_cost
# timestamp is YYYY-MM-DDTHH:MM in UTC. stored_cost is what the provider recorded
# for that request. One request is one billable provider call.
#
# Costs are USD. Peak hours are Monday-Friday 01:00-04:00 and 06:00-10:00 UTC;
# every other time, including weekends, is off-peak. Cache write is not priced
# and reasoning is billed at the output rate.
#
# Without an explicit range the report covers the first through the last request
# day. Every day in the range is reported, including days with no requests.

Feature: DeepSeek Per-Request Report

  Scenario Outline: DeepSeek Per-Request Report 1 - each request counts once on the day it was made
    Given the requests <requests>
    When the DeepSeek report is generated
    Then the day <day> reports a request count of <requests_count>

    Examples:
      | requests | day | requests_count |
      | 2026-09-07T00:10,opencode-go,deepseek-v4.1-flash,1000000,500000,0,0,0,0.45 | 09/07 | 1 |
      | 2026-09-07T00:10,opencode-go,deepseek-v4.1-flash,1000000,500000,0,0,0,0.45;2026-09-07T04:30,opencode-go,deepseek-v4.1-flash,0,0,0,1000000,100,0.003 | 09/07 | 2 |
      | 2026-09-07T00:10,opencode-go,deepseek-v4.1-flash,1000000,500000,0,0,0,0.45;2026-09-08T00:10,opencode-go,deepseek-v4.1-flash,2000000,0,0,0,0,0.30 | 09/07 | 1 |
      | 2026-09-07T00:10,opencode-go,deepseek-v4.1-flash,1000000,500000,0,0,0,0.45;2026-09-08T00:10,opencode-go,deepseek-v4.1-flash,2000000,0,0,0,0,0.30 | 09/08 | 1 |

  Scenario Outline: DeepSeek Per-Request Report 2 - input tokens are summed per day
    Given the requests <requests>
    When the DeepSeek report is generated
    Then the day <day> reports <input> input tokens

    Examples:
      | requests | day | input |
      | 2026-09-08T00:10,opencode-go,deepseek-v4.1-flash,1000000,500000,0,0,0,0.45 | 09/08 | 1000000 |
      | 2026-09-07T00:10,opencode-go,deepseek-v4.1-flash,1000000,500000,0,0,0,0.45;2026-09-07T04:30,opencode-go,deepseek-v4.1-flash,2000000,0,0,0,0,0.30 | 09/07 | 3000000 |

  Scenario Outline: DeepSeek Per-Request Report 3 - output tokens are output plus reasoning per day
    Given the requests <requests>
    When the DeepSeek report is generated
    Then the day <day> reports <output> output tokens

    Examples:
      | requests | day | output |
      | 2026-09-08T00:10,opencode-go,deepseek-v4.1-flash,0,300000,200000,0,0,0.30 | 09/08 | 500000 |
      | 2026-09-07T00:10,opencode-go,deepseek-v4.1-flash,0,300000,200000,0,0,0.30;2026-09-07T04:30,opencode-go,deepseek-v4.1-flash,0,100000,0,0,0,0.06 | 09/07 | 600000 |

  Scenario Outline: DeepSeek Per-Request Report 4 - cache read tokens are summed per day
    Given the requests <requests>
    When the DeepSeek report is generated
    Then the day <day> reports <cache_read> cache read tokens

    Examples:
      | requests | day | cache_read |
      | 2026-09-08T04:30,opencode-go,deepseek-v4.1-flash,0,0,0,1000000,0,0.003 | 09/08 | 1000000 |
      | 2026-09-07T04:30,opencode-go,deepseek-v4.1-flash,0,0,0,1000000,0,0.003;2026-09-07T05:00,opencode-go,deepseek-v4.1-flash,0,0,0,2000000,0,0.006 | 09/07 | 3000000 |

  Scenario Outline: DeepSeek Per-Request Report 5 - cache write tokens are summed per day
    Given the requests <requests>
    When the DeepSeek report is generated
    Then the day <day> reports <cache_write> cache write tokens

    Examples:
      | requests | day | cache_write |
      | 2026-09-08T04:30,opencode-go,deepseek-v4.1-flash,0,0,0,0,100,0 | 09/08 | 100 |
      | 2026-09-07T04:30,opencode-go,deepseek-v4.1-flash,0,0,0,0,100,0;2026-09-07T05:00,opencode-go,deepseek-v4.1-flash,0,0,0,0,200,0 | 09/07 | 300 |

  Scenario Outline: DeepSeek Per-Request Report 6 - Go-reported cost is the stored cost of Go requests per day
    Given the requests <requests>
    When the DeepSeek report is generated
    Then the day <day> reports Go-reported cost <go_reported> rounded to 6 decimal places

    Examples:
      | requests | day | go_reported |
      | 2026-09-08T02:00,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0.15 | 09/08 | 0.15 |
      | 2026-09-07T02:00,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0.15;2026-09-07T04:30,opencode-go,deepseek-v4.1-flash,0,0,0,1000000,0,0.003 | 09/07 | 0.153 |

  Scenario Outline: DeepSeek Per-Request Report 7 - peak-aware cost picks the rate of the hour each request was made
    Given the requests <requests>
    When the DeepSeek report is generated
    Then the day <day> reports peak-aware cost <go_cost> rounded to 6 decimal places

    Examples:
      | requests | day | go_cost |
      | 2026-09-08T02:00,opencode-go,deepseek-v4.1-flash,1000000,300000,200000,0,0,0.45 | 09/08 | 0.9 |
      | 2026-09-07T02:00,opencode-go,deepseek-v4.1-flash,1000000,300000,200000,0,0,0.45;2026-09-07T04:30,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0.15 | 09/07 | 1.05 |

  Scenario Outline: DeepSeek Per-Request Report 8 - peak is weekday 01:00-04:00 and 06:00-10:00 UTC
    Given the requests <requests>
    When the DeepSeek report is generated
    Then the day <day> reports peak-aware cost <go_cost> rounded to 6 decimal places

    Examples:
      | requests | day | go_cost |
      | 2026-09-07T00:00,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0 | 09/07 | 0.15 |
      | 2026-09-07T00:59,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0 | 09/07 | 0.15 |
      | 2026-09-07T01:00,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0 | 09/07 | 0.3 |
      | 2026-09-07T03:59,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0 | 09/07 | 0.3 |
      | 2026-09-07T04:00,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0 | 09/07 | 0.15 |
      | 2026-09-07T05:59,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0 | 09/07 | 0.15 |
      | 2026-09-07T06:00,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0 | 09/07 | 0.3 |
      | 2026-09-07T09:59,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0 | 09/07 | 0.3 |
      | 2026-09-07T10:00,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0 | 09/07 | 0.15 |
      | 2026-09-07T23:59,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0 | 09/07 | 0.15 |
      | 2026-09-05T02:00,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0 | 09/05 | 0.15 |
      | 2026-09-06T02:00,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0 | 09/06 | 0.15 |

  Scenario Outline: DeepSeek Per-Request Report 9 - requests outside the Go provider are counted but carry no Go cost
    Given the requests <requests>
    When the DeepSeek report is generated
    Then the day <day> reports a request count of <requests_count>
    And the day <day> reports Go-reported cost <go_reported> rounded to 6 decimal places
    And the day <day> reports peak-aware cost <go_cost> rounded to 6 decimal places

    Examples:
      | requests | day | requests_count | go_reported | go_cost |
      | 2026-09-07T00:10,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0.15;2026-09-07T00:20,deepseek,deepseek-v4.1-flash,1000000,0,0,0,0,0.10 | 09/07 | 2 | 0.15 | 0.15 |

  Scenario Outline: DeepSeek Per-Request Report 10 - each model is priced at its own rates
    Given the requests <requests>
    When the DeepSeek report is generated
    Then the day <day> reports peak-aware cost <go_cost> rounded to 6 decimal places

    Examples:
      | requests | day | go_cost |
      | 2026-09-07T00:10,opencode-go,deepseek-v4.1-flash,1000000,500000,0,0,0,0.45 | 09/07 | 0.45 |
      | 2026-09-08T00:10,opencode-go,deepseek-v4-flash,1000000,500000,0,0,0,0.45 | 09/08 | 0.45 |
      | 2026-09-07T00:10,opencode-go,deepseek-v4-pro,1000000,500000,0,0,0,0.66 | 09/07 | 1.65 |
      | 2026-09-08T00:10,opencode-go,deepseek-v4-flash-vision-exp,1000000,500000,0,0,0,0.45 | 09/08 | 0.45 |
      | 2026-09-07T00:10,opencode-go,deepseek-flash,1000000,500000,0,0,0,0.45 | 09/07 | 0.45 |

  Scenario Outline: DeepSeek Per-Request Report 11 - cache writes are counted but not priced
    Given the requests <requests>
    When the DeepSeek report is generated
    Then the day <day> reports <cache_write> cache write tokens
    And the day <day> reports peak-aware cost <go_cost> rounded to 6 decimal places

    Examples:
      | requests | day | cache_write | go_cost |
      | 2026-09-07T00:10,opencode-go,deepseek-v4.1-flash,0,0,0,0,1000000,0 | 09/07 | 1000000 | 0 |

  Scenario Outline: DeepSeek Per-Request Report 12 - every day in the range is reported
    Given the requests 2026-09-08T00:10,opencode-go,deepseek-v4.1-flash,1000000,0,0,0,0,0.15
    And the report covers 2026-09-07 through 2026-09-09
    When the DeepSeek report is generated
    Then the day <day> reports a request count of <requests_count>
    And the day <day> reports <input> input tokens
    And the day <day> reports Go-reported cost <go_reported> rounded to 6 decimal places

    Examples:
      | day | requests_count | input | go_reported |
      | 09/07 | 0 | 0 | 0 |
      | 09/08 | 1 | 1000000 | 0.15 |
      | 09/09 | 0 | 0 | 0 |
