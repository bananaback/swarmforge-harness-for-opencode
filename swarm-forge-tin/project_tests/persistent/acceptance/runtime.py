"""Acceptance runtime -- shared execution engine for Gherkin scenarios.

Self-contained copy of the harness runtime, per the constitution: the project's
acceptance runtime lives under the configured persistent test root.
"""

import re
from collections.abc import Callable
from typing import Any


class World:
    """Fresh state object for each scenario execution."""

    def __init__(self) -> None:
        self.state: dict[str, Any] = {}


StepHandler = Callable[[World, dict[str, str]], None]


class Runtime:
    """Execute acceptance scenarios against registered step handlers."""

    def __init__(self) -> None:
        self._handlers: list[tuple[re.Pattern[str], StepHandler]] = []

    def register(self, pattern: str, handler: StepHandler) -> None:
        """Register a regex step handler."""
        self._handlers.append((re.compile(pattern), handler))

    def _find_handler(self, step_text: str) -> StepHandler:
        for regex, handler in self._handlers:
            if regex.search(step_text):
                return handler
        raise RuntimeError(f"Unsupported step: {step_text}")

    def _resolve_text(self, text: str, examples: dict[str, str]) -> str:
        def _sub(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in examples:
                raise RuntimeError(f"Missing example value for <{name}>")
            return examples[name]

        resolved = re.sub(r"<([A-Za-z0-9_]+)>", _sub, text)
        if resolved.startswith('"') and resolved.endswith('"'):
            resolved = resolved[1:-1]
        return resolved.replace("\\n", "\n").replace("\\t", "\t")

    def _execute_step(self, step: dict, examples: dict[str, str], world: World) -> None:
        handler = self._find_handler(step["text"])
        resolved = dict(examples)
        resolved["_step_text"] = step["text"]
        for param in step.get("parameters", []):
            if param in resolved:
                resolved[param] = self._resolve_text(f"<{param}>", examples)
        handler(world, resolved)

    def run_scenario(self, scenario: dict, background: list[dict] | None = None) -> None:
        """Run a scenario once per example row with a fresh World."""
        examples_list = scenario.get("examples", []) or [{}]
        for examples in examples_list:
            world = World()
            for step in background or []:
                self._execute_step(step, examples, world)
            for step in scenario["steps"]:
                self._execute_step(step, examples, world)

    def run_all(self, ir: dict) -> None:
        """Run all scenarios from the JSON IR."""
        background = ir.get("background", [])
        for scenario in ir["scenarios"]:
            self.run_scenario(scenario, background)
