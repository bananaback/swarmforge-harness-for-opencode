Feature: Duplicate dispatch

  # A role dispatched twice runs two sessions against one queue. The per-role
  # lock and item ownership let exactly one session claim the item; the
  # duplicate is refused as a foreign owner and stops instead of continuing.

  Background:
    Given a temporary project with its own state root

  # Duplicate dispatch 1 - simultaneous duplicate pulls leave exactly one owner
  Scenario: Duplicate dispatch 1 - simultaneous duplicate pulls leave exactly one owner
    Given mails "feature/periods@50" are queued to "coder"
    When sessions "session-a" and "session-b" pull the "coder" mail at the same time
    Then exactly one session claims the item
    And the losing session is refused naming the winning session
