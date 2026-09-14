#!/usr/bin/env python3
"""Runner adapter: execute generated acceptance tests against a mutated IR.

Implements the persistent worker protocol in ``tools/aps/mutator-spec.md``: one
newline-delimited JSON job per input line, one response per output line. The
adapter runs the generated pytest entry points with ``SWARM_ACCEPTANCE_IR``
pointing at the mutated IR, so the same generated tests evaluate every mutant.
Standard output carries protocol data only; diagnostics stay in the response.
"""

import json
import os
import subprocess
import sys
import time

IR_ENV = "SWARM_ACCEPTANCE_IR"


def classify(returncode):
    """Map a pytest exit code to a mutator runner outcome."""
    if returncode == 0:
        return "test_success"
    if returncode == 1:
        return "test_failure"
    return "infrastructure_error"


def run_job(job, python=None):
    """Run one mutation job and return the protocol response dict."""
    python = python or sys.executable
    generated_dir = str(job["generated_dir"])
    feature_json = str(job["feature_json"])
    env = dict(os.environ)
    env[IR_ENV] = feature_json
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic_ns()
    try:
        proc = subprocess.run(
            [python, "-m", "pytest", generated_dir, "-q", "-p", "no:cacheprovider"],
            cwd=generated_dir,
            env=env,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        return _response(job, "infrastructure_error", "", str(error), started)
    outcome = classify(proc.returncode)
    error = proc.stderr if outcome == "infrastructure_error" else ""
    return _response(job, outcome, proc.stdout, error, started)


def _response(job, outcome, output, error, started):
    return {
        "id": job.get("id", ""),
        "outcome": outcome,
        "output": output,
        "error": error,
        "duration": time.monotonic_ns() - started,
    }


def serve(stdin, stdout):
    """Answer newline-delimited JSON jobs until end of input."""
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        response = _handle(line)
        stdout.write(json.dumps(response) + "\n")
        stdout.flush()


def _handle(line):
    try:
        job = json.loads(line)
    except json.JSONDecodeError as error:
        return {
            "id": "",
            "outcome": "infrastructure_error",
            "output": "",
            "error": f"malformed job request: {error}",
            "duration": 0,
        }
    return run_job(job)


def main():
    serve(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
