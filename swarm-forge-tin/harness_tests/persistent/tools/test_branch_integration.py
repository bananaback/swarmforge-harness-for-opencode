"""M9 end-to-end: the design branch and the execution branch converge.

This is the milestone's validation run. It drives
``specifier -> designer -> task-breaker -> coder -> refactorer -> architect``
through the real mailbox, team, and taskbreak CLIs on a scratch project and
asserts every documented seam:

* the designer's seed reaches the task-breaker and the coder chunk;
* ``taskbreak`` opens each planned chunk and the coder chunk carries both the
  specifier mail and the design seed;
* forward handoffs, ``team_close``, and ``team status --ready`` drain clean;
* the recovery paths (ask/brief, a red attempt, an interrupted pull, an unbound
  session) behave as documented.

The run writes a machine-readable run log to the scratch project's artifacts
root and to ``$SWARM_E2E_RUNLOG`` when set, so the milestone evidence is
reproducible.
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import team
from support import env_without_swarm, project_config, run_tool

MAILBOX = "mailbox.py"
TEAM = "team.py"
TASKBREAK = "taskbreak.py"

PACK = Path(__file__).resolve().parents[3]
TOOLS = PACK / "tools"

ROLES = [
    "orchestrator",
    "specifier",
    "designer",
    "task-breaker",
    "coder",
    "refactorer",
    "architect",
    "mentor",
]

SESSIONS = {
    "orchestrator": "ses-orch",
    "specifier": "ses-spec",
    "designer": "ses-design",
    "task-breaker": "ses-tb",
    "coder": "ses-coder",
    "mentor": "ses-mentor",
    "refactorer": "ses-ref",
    "architect": "ses-arch",
}

ORACLE = (
    f"{sys.executable} -c \"from src.cart import total; "
    "assert total([1, 2]) == 3; print('cart oracle green')\""
)
RED_ORACLE = f"{sys.executable} -c \"raise SystemExit(3)\""

DESIGN_SEED = (
    "TASK\n"
    "Build the cart total.\n\n"
    "DEFINITION OF DONE\n"
    "- [ ] the total of the items is their sum\n\n"
    "INTERFACE CONTRACT\n"
    "class Cart:\n"
    "    def total(self, items): ...\n\n"
    "FILES\n"
    "- src/cart.py -- Cart\n"
)

BRIEF = (
    "TASK\n"
    "Implement the cart total.\n\n"
    "DEFINITION OF DONE\n"
    "- [ ] src.cart.total sums the items\n"
)


def today():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def _git(project, *args):
    subprocess.run(
        ["git", *args], cwd=project, capture_output=True, text=True
    )


def make_scratch(tmp_path):
    """Build a minimal project the pipeline can run against from scratch."""
    project, config = project_config(
        tmp_path,
        name="scratch",
        state_root="state",
        artifacts_root="artifacts",
        hot_tests="hot",
        persistent_tests=[{"root": "tests", "pythonpath": ["."], "kind": "project"}],
        source_roots=["src"],
        features="features",
        roles=ROLES,
    )
    for rel in ("features/design", "src", "tests/unit", "artifacts", "hot"):
        (project / rel).mkdir(parents=True, exist_ok=True)
    (project / "src" / "cart.py").write_text(
        "def total(items):\n    return sum(items)\n"
    )
    feature = project / "features" / "cart.feature"
    feature.write_text(
        "Feature: Cart\n\n"
        "  Scenario: total of two items\n"
        "    Given a cart with items 1 and 2\n"
        "    Then the total is 3\n"
    )
    _git(project, "init")
    _git(project, "config", "user.email", "e2e@example.test")
    _git(project, "config", "user.name", "E2E")
    (project / ".gitignore").write_text("state/\nartifacts/\nhot/\n")
    _git(project, "add", ".")
    _git(project, "commit", "-m", "scratch init")
    return project, config, feature


class E2E:
    """Recorded driver for one scratch run of both branches."""

    def __init__(self, project, config):
        self.project = project
        self.config = config
        self.log = []

    def _record(self, label, argv, result):
        self.log.append(
            {
                "step": label,
                "argv": [str(arg) for arg in argv],
                "exit": result.returncode,
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-2000:],
            }
        )

    def tool(self, script, *args, label=None, check=True):
        result = run_tool(script, self.project, self.config, *args)
        self._record(label or f"{script} {args[0] if args else ''}", [script, *args], result)
        if check:
            assert result.returncode == 0, (
                f"{script} {' '.join(str(a) for a in args)} failed "
                f"(exit {result.returncode}):\n{result.stderr}"
            )
        return result

    def raw(self, argv, label=None, check=True):
        result = subprocess.run(
            [str(arg) for arg in argv],
            cwd=str(self.project),
            env=env_without_swarm(SWARM_CONFIG=self.config),
            capture_output=True,
            text=True,
        )
        self._record(label or Path(argv[0]).name, argv, result)
        if check:
            assert result.returncode == 0, f"{argv} failed:\n{result.stderr}"
        return result

    def mail(self, *args, **kwargs):
        return self.tool(MAILBOX, *args, **kwargs)

    def team(self, *args, **kwargs):
        return self.tool(TEAM, *args, **kwargs)

    def write_runlog(self):
        payload = {"milestone": "M9", "feature": "cart", "steps": self.log}
        text = json.dumps(payload, indent=2, sort_keys=True)
        dest = self.project / "artifacts" / "m9" / "runlog.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
        override = os.environ.get("SWARM_E2E_RUNLOG")
        if override:
            target = Path(override)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        return payload


def _start(mail, recipient, message, session):
    return mail(
        "send",
        "--from",
        "orchestrator",
        "--to",
        recipient,
        "--task",
        "cart",
        "--message",
        message,
        "--session",
        session,
    )


def test_design_and_execution_branches_converge(tmp_path):
    project, config, feature = make_scratch(tmp_path)
    e2e = E2E(project, config)
    s = SESSIONS

    # --- execution branch: the specifier turns intent into a parsed feature ---
    _start(e2e.mail, "specifier", "build the cart (features/cart.feature)", s["orchestrator"])
    spec = e2e.mail("pull", "--as", "specifier", "--session", s["specifier"])
    assert "TASK_NAME: cart" in spec.stdout

    ir = project / "artifacts" / "cart.json"
    if shutil.which("bb"):
        e2e.raw([TOOLS / "gherkin-parser", feature, ir], label="specifier parse")
    else:
        ir.write_text(json.dumps({"name": "cart", "scenarios": []}))
        e2e.log.append(
            {
                "step": "specifier parse (staged; babashka absent)",
                "argv": [],
                "exit": 0,
                "stdout": "",
                "stderr": "",
            }
        )
    assert ir.is_file()

    e2e.mail("send", "--from", "specifier", "--to", "coder",
             "--task", "cart", "--message", "spec: features/cart.feature; IR artifacts/cart.json",
             "--session", s["specifier"])
    e2e.mail("done", "--as", "specifier", "--session", s["specifier"])
    assert not list((project / "state" / "mail" / "inbox" / "specifier" / "in_process").glob("*.json"))

    # --- design branch: designer -> task-breaker -> taskbreak.py ---
    _start(e2e.mail, "designer", "design the cart (features/cart.feature)", s["orchestrator"])
    designer = e2e.mail("pull", "--as", "designer", "--session", s["designer"])
    assert "cart.feature" in designer.stdout

    seed = project / "features" / "design" / "cart.md"
    seed.write_text(DESIGN_SEED)
    e2e.mail("send", "--from", "designer", "--to", "task-breaker",
             "--task", "cart", "--message", "seed: features/design/cart.md",
             "--session", s["designer"])
    e2e.mail("done", "--as", "designer", "--session", s["designer"])

    breaker = e2e.mail("pull", "--as", "task-breaker", "--session", s["task-breaker"])
    assert "TASK_NAME: cart" in breaker.stdout
    assert seed.is_file(), "the designer's seed was not readable by the task-breaker"

    plan = project / "artifacts" / "taskbreak" / "cart.plan.json"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        json.dumps(
            {
                "version": 1,
                "feature": "features/cart.feature",
                "chunks": [
                    {
                        "task": "cart",
                        "role": "coder",
                        "brief_text": BRIEF,
                        "design": "features/design/cart.md",
                        "oracle": ORACLE,
                        "goal": "cart total green",
                        "rules": "one job per function",
                    }
                ],
            }
        )
    )
    e2e.mail("done", "--as", "task-breaker", "--session", s["task-breaker"])

    opened = e2e.tool(TASKBREAK, "--plan", str(plan), label="taskbreak open")
    assert "OPENED: cart" in opened.stdout

    task_dir = project / "state" / "tasks" / today() / "cart"
    doc = json.loads((task_dir / "task.json").read_text())
    assert doc["role"] == "coder"
    assert doc["design_input"].endswith(".design.md")
    inputs = task_dir / "01-coder" / "input"
    assert (inputs / "cart.feature").is_file()
    assert (inputs / "cart.json").is_file()
    assert (inputs / doc["design_input"]).read_text() == DESIGN_SEED

    # --- convergence: the coder chunk carries the specifier mail + design seed ---
    e2e.team("bind", "cart", "--seat", "worker", "--session", s["coder"])
    pull = e2e.team("pull", "--session", s["coder"])
    assert "TASK: cart/worker" in pull.stdout
    coder_mail = e2e.mail("pull", "--as", "coder", "--session", s["coder"])
    assert "TASK_NAME: cart" in coder_mail.stdout
    assert "FROM: specifier" in coder_mail.stdout

    context = e2e.team("context", "--session", s["coder"])
    assert context.stdout.splitlines()[0] == "TASK"
    assert "class Cart" in context.stdout, "the coder chunk is missing the design seed"
    assert "DEFINITION OF DONE" in context.stdout

    # --- the coder peer: journal, oracle, ask/brief ---
    e2e.team("bind", "cart", "--seat", "mentor", "--session", s["mentor"])
    e2e.team("journal", "--session", s["coder"], "--kind", "readback",
             "--entry", json.dumps({"goal": "cart total green"}))
    e2e.team("journal", "--session", s["coder"], "--kind", "plan",
             "--entry", json.dumps({"choice": "implement sum"}))
    attempt = e2e.team("attempt", "--session", s["coder"], "--command", ORACLE)
    assert "ATTEMPT: 1" in attempt.stdout
    assert "EXIT: 0" in attempt.stdout
    e2e.team("journal", "--session", s["coder"], "--kind", "result",
             "--entry", json.dumps({"reading": "green"}), "--attempt", "1")

    e2e.team("send", "--session", s["coder"], "--to", "mentor",
             "--kind", "ask", "--message", "review the total boundary?")
    e2e.team("send", "--session", s["mentor"], "--to", "worker",
             "--kind", "brief", "--message", "keep the sum, move on")
    mentor_context = e2e.team("context", "--session", s["mentor"])
    assert mentor_context.stdout.startswith(team.MENTOR_SYSTEM_PROMPT)
    assert "review the total boundary?" in mentor_context.stdout

    # --- forward handoff, then close the coder chunk ---
    e2e.mail("send", "--from", "coder", "--to", "refactorer",
             "--task", "cart", "--message", "touched: src/cart.py; oracle green",
             "--session", s["coder"])
    e2e.mail("done", "--as", "coder", "--session", s["coder"])
    e2e.team("done", "--session", s["coder"])
    e2e.team("close", "cart")

    # --- refactorer phase chunk (nested id, per the documented chunk naming) ---
    ref_task = "cart/refactorer"
    ref_brief = project / "refactorer.brief.md"
    ref_brief.write_text(BRIEF)
    e2e.team("open", ref_task, "--role", "refactorer",
             "--brief", str(ref_brief),
             "--feature", str(feature),
             "--design", str(seed))
    ready = e2e.team("status", "--ready")
    assert f"READY: {ref_task} worker SPAWN_PENDING" in ready.stdout, (
        "team status --ready cannot see the nested phase chunk"
    )
    e2e.team("bind", ref_task, "--seat", "worker", "--session", s["refactorer"])
    e2e.team("pull", "--session", s["refactorer"])
    ref_mail = e2e.mail("pull", "--as", "refactorer", "--session", s["refactorer"])
    assert "FROM: coder" in ref_mail.stdout
    e2e.team("context", "--session", s["refactorer"])
    ref_attempt = e2e.team("attempt", "--session", s["refactorer"], "--command", ORACLE)
    assert "EXIT: 0" in ref_attempt.stdout
    e2e.team("journal", "--session", s["refactorer"], "--kind", "result",
             "--entry", json.dumps({"reading": "behaviour preserved"}))
    e2e.mail("send", "--from", "refactorer", "--to", "architect",
             "--task", "cart", "--message", "touched: src/cart.py; still green",
             "--session", s["refactorer"])
    e2e.mail("done", "--as", "refactorer", "--session", s["refactorer"])
    e2e.team("done", "--session", s["refactorer"])
    e2e.team("close", ref_task)

    # --- architect phase chunk: the final gate ---
    arch_task = "cart/architect"
    arch_brief = project / "architect.brief.md"
    arch_brief.write_text(BRIEF)
    e2e.team("open", arch_task, "--role", "architect",
             "--brief", str(arch_brief),
             "--feature", str(feature),
             "--design", str(seed))
    e2e.team("bind", arch_task, "--seat", "worker", "--session", s["architect"])
    e2e.team("pull", "--session", s["architect"])
    arch_mail = e2e.mail("pull", "--as", "architect", "--session", s["architect"])
    assert "FROM: refactorer" in arch_mail.stdout
    arch_attempt = e2e.team("attempt", "--session", s["architect"], "--command", ORACLE)
    assert "EXIT: 0" in arch_attempt.stdout
    e2e.team("journal", "--session", s["architect"], "--kind", "note",
             "--entry", json.dumps({"reading": "boundaries hold"}))
    e2e.mail("done", "--as", "architect", "--session", s["architect"])
    e2e.team("done", "--session", s["architect"])
    e2e.team("close", arch_task)

    # --- drain: no ready seats, no queued or in-process mail ---
    drained = e2e.team("status", "--ready")
    assert "READY: none" in drained.stdout
    mail = e2e.mail("status", "--json")
    report = json.loads(mail.stdout)["roles"]
    for role, entry in report.items():
        assert entry["counts"]["new"] == 0, f"{role} still has queued mail"
        assert entry["counts"]["in_process"] == 0, f"{role} still holds mail"

    e2e.write_runlog()


def test_recovery_paths_behave_as_documented(tmp_path):
    project, config, _ = make_scratch(tmp_path)
    e2e = E2E(project, config)
    red_brief = project / "recovery.brief.md"
    red_brief.write_text(BRIEF)
    e2e.team("open", "recovery", "--role", "coder", "--brief", str(red_brief))
    e2e.team("bind", "recovery", "--seat", "worker", "--session", "ses-worker")

    # an interrupted pull resumes the same item
    first = e2e.team("pull", "--session", "ses-worker")
    assert "TASK: recovery/worker" in first.stdout
    resumed = e2e.team("pull", "--session", "ses-worker")
    assert "RESUMED: yes" in resumed.stdout
    assert first.stdout.splitlines()[0] == resumed.stdout.splitlines()[0]

    # an unbound session is a hard refusal
    ghost = e2e.team("pull", "--session", "ses-ghost", check=False)
    assert ghost.returncode == 2
    assert "not bound to any team seat" in ghost.stderr

    # a red oracle is recorded as a failed attempt, not hidden
    red = e2e.team("attempt", "--session", "ses-worker", "--command", RED_ORACLE)
    assert "EXIT: 3" in red.stdout
    e2e.team("journal", "--session", "ses-worker", "--kind", "result",
             "--entry", json.dumps({"reading": "red"}), "--attempt", "1")
    journal = (
        project / "state" / "tasks" / today() / "recovery" / "01-coder" / "journal.jsonl"
    ).read_text()
    result = json.loads(journal.splitlines()[-1])
    assert result["kind"] == "result"
    assert result["exit"] == 3

    e2e.team("done", "--session", "ses-worker")
