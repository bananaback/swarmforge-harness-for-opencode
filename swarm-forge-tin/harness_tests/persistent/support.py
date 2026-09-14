"""Shared helpers for harness tests."""

import os


def env_without_swarm(**extra):
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("SWARM_")
    }
    env.update({key: str(value) for key, value in extra.items()})
    return env
