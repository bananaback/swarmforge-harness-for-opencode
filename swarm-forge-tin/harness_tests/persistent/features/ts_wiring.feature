Feature: TS wiring

  # The opencode TypeScript bridges resolve the harness config with the same
  # order as the Python resolver: environment, nearest config walking up, the
  # pack override, then the pack config. With no start they walk up from the
  # working directory and fall back to the pack that provides the resolver.

  Background:
    Given no harness environment overrides

  # TS wiring 1 - no start walks up to the nearest config
  # Rationale: the TS resolver skipped walk-up when no start was given, so it
  # now walks up from the working directory like the Python resolver.
  Scenario: TS wiring 1 - no start walks up to the nearest config
    Given a temporary project with its own harness config
    And a nested working directory under that project
    When the TS config is resolved with no start from the nested working directory
    Then the TS resolver reports the project config

  # TS wiring 2 - no start falls back to the pack config
  # Rationale: the TS resolver had no pack-root fallback, so it now falls back
  # to the pack config after the environment and walk-up fail.
  Scenario: TS wiring 2 - no start falls back to the pack config
    Given a working directory with no harness config above it
    When the TS config is resolved with no start
    Then the TS resolver reports the harness pack config
