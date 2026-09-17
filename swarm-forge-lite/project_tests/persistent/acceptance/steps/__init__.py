"""Registered acceptance step handlers for the wired project.

Each feature area exports a ``HANDLERS`` list of ``(pattern, handler)`` pairs;
``STEP_HANDLERS`` concatenates them in registration order.
"""

from .deepseek_report import HANDLERS as DEEPSEEK_REPORT
from .token_usage import HANDLERS as TOKEN_USAGE

STEP_HANDLERS = [
    *TOKEN_USAGE,
    *DEEPSEEK_REPORT,
]
