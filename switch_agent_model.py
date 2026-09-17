#!/usr/bin/env python3
"""Switch the model used by every agent in .opencode/agents.

Usage:
    python3 switch_agent_model.py deepseek
    python3 switch_agent_model.py union
    python3 switch_agent_model.py toggle

deepseek -> opencode-go/deepseek-v4.1-flash plus variant, temperature, top_p
union    -> opencode-go/union-alpha with those sampling keys removed
toggle   -> flip to the model that is not currently set
"""

from __future__ import annotations

import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent / ".opencode" / "agents"

DEEPSEEK_MODEL = "opencode-go/deepseek-v4.1-flash"
UNION_MODEL = "opencode-go/union-alpha"

DEEPSEEK_PARAMS = (("variant", "high"), ("temperature", "1"), ("top_p", "0.95"))
UNION_PARAMS = ()

MODEL_KEY = "model:"
MANAGED_KEYS = tuple(f"{key}:" for key, _ in DEEPSEEK_PARAMS)


def frontmatter_end(lines):
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing opening frontmatter delimiter")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return index
    raise ValueError("missing closing frontmatter delimiter")


def current_model(text):
    lines = text.splitlines()
    end = frontmatter_end(lines)
    for line in lines[1:end]:
        if line.startswith(MODEL_KEY):
            return line.split(":", 1)[1].strip()
    return None


def rewrite(text, model, params):
    lines = text.splitlines(keepends=True)
    end = frontmatter_end(lines)
    front = lines[1:end]
    out = []
    model_seen = False
    for line in front:
        stripped = line.strip()
        indent = line[: len(line) - len(line.lstrip())]
        if stripped.startswith(MODEL_KEY):
            model_seen = True
            out.append(f"{indent}{MODEL_KEY} {model}\n")
            for key, value in params:
                out.append(f"{indent}{key}: {value}\n")
        elif any(stripped.startswith(key) for key in MANAGED_KEYS):
            continue
        else:
            out.append(line)
    if not model_seen:
        raise ValueError("no model line in frontmatter")
    return "".join(lines[:1] + out + lines[end:])


def target_for(request, text):
    if request == "toggle":
        return "union" if current_model(text) == DEEPSEEK_MODEL else "deepseek"
    return request


def main(argv):
    if len(argv) != 2 or argv[1] not in ("deepseek", "union", "toggle"):
        print(__doc__)
        return 2

    files = sorted(AGENTS_DIR.glob("*.md"))
    if not files:
        print(f"no agent files under {AGENTS_DIR}", file=sys.stderr)
        return 1

    changed = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        target = target_for(argv[1], text)
        if target == "deepseek":
            updated = rewrite(text, DEEPSEEK_MODEL, DEEPSEEK_PARAMS)
        else:
            updated = rewrite(text, UNION_MODEL, UNION_PARAMS)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed += 1
        print(f"{path.name}: {target}")

    print(f"{changed} file(s) changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
