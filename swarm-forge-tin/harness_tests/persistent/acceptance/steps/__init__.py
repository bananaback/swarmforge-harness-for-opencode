"""Acceptance step handlers, grouped by the feature job each one serves.

Every submodule owns one acceptance feature area and exports a ``HANDLERS``
list of ``(pattern, handler)`` pairs. ``STEP_HANDLERS`` concatenates them in the
original registration order, so the generated acceptance entry points still
register exactly one handler per step shape.
"""

from .acceptance_pipeline_steps import HANDLERS as _PIPELINE_HANDLERS
from .coder_payload_steps import HANDLERS as _CODER_HANDLERS
from .durable_store_steps import HANDLERS as _DURABLE_STORE_HANDLERS
from .harness_cli_steps import HANDLERS as _HARNESS_CLI_HANDLERS
from .harness_portability_steps import HANDLERS as _PORTABILITY_HANDLERS
from .mail_steps import HANDLERS as _MAIL_HANDLERS
from .mentor_payload_steps import HANDLERS as _MENTOR_HANDLERS
from .task_state_steps import HANDLERS as _TASK_STATE_HANDLERS
from .taskbreak_steps import HANDLERS as _TASKBREAK_HANDLERS
from .team_open_steps import HANDLERS as _TEAM_OPEN_HANDLERS
from .team_steps import HANDLERS as _TEAM_HANDLERS
from .ts_wiring_steps import HANDLERS as _TS_WIRING_HANDLERS
from .wiring_steps import HANDLERS as _WIRING_HANDLERS

STEP_HANDLERS = [
    *_CODER_HANDLERS,
    *_HARNESS_CLI_HANDLERS,
    *_WIRING_HANDLERS,
    *_PORTABILITY_HANDLERS,
    *_TS_WIRING_HANDLERS,
    *_TASK_STATE_HANDLERS,
    *_MENTOR_HANDLERS,
    *_MAIL_HANDLERS,
    *_TEAM_HANDLERS,
    *_TASKBREAK_HANDLERS,
    *_DURABLE_STORE_HANDLERS,
    *_PIPELINE_HANDLERS,
    *_TEAM_OPEN_HANDLERS,
]
