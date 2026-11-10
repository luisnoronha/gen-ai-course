"""The accumulated case set, run several times per version.

Cases come from Sessions 1 and 2, plus any case the students add to starter/cases/.
Each run is checked twice: by the case's checks (meridian.evaluate) and by the
trajectory checks of starter/trajectory.py.
"""

from __future__ import annotations

import importlib.util
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from meridian.agent_runtime import IncidentRun, run_incident

import agents

COURSE = agents.HERE.parents[1]
CASE_DIRS = (
    COURSE / "01-agent-harness" / "cases",
    COURSE / "02-context-tools-skills" / "cases",
    agents.STARTER / "cases",
)


def cases() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for directory in CASE_DIRS:
        for path in sorted(directory.glob("*.yaml")):
            found[path.stem] = path
    return found


def load_starter(name: str):
    """A students' file from starter/, loaded fresh so edits apply without restarting the app."""
    spec = importlib.util.spec_from_file_location(f"s06_{name}", agents.STARTER / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"s06_{name}"] = module
    spec.loader.exec_module(module)
    return module


def trajectory_checks() -> list[Callable[[IncidentRun], tuple[bool, str]]]:
    """The functions listed in starter/trajectory.py (CHECKS). Unwritten ones are skipped."""
    return list(getattr(load_starter("trajectory"), "CHECKS", []))


def describe(run: IncidentRun) -> str:
    """What the critic sees about a run: starter/critic.py, or only the agent's own words."""
    try:
        return load_starter("critic").describe_run(run)
    except NotImplementedError:
        report = run.report
        if report is None:
            return f"The run ended without a report ({run.error})."
        return f"Status reported by the agent: {report.status}\nSummary: {report.summary}"


@dataclass
class RunResult:
    version: str
    case: str
    passed: bool
    failed: list[str]
    tokens: int
    requests: int
    status: str
    summary: str
    error: str | None = None
    trajectory: dict[str, str] = field(default_factory=dict)
    actions: list[str] = field(default_factory=list)
    description: str = ""  # what the critic sees

    @property
    def row(self) -> dict[str, Any]:
        return {"Version": self.version, "Case": self.case, "Pass": self.passed, "Status": self.status,
                "Failed checks": "; ".join(self.failed) or "-", "Input tokens": self.tokens, "Requests": self.requests}


def _check_trajectory(run: IncidentRun, checks) -> tuple[bool, dict[str, str], list[str]]:
    passed, notes, failed = True, {}, []
    for check in checks:
        name = check.__name__
        try:
            ok, detail = check(run)
        except NotImplementedError:
            notes[name] = "not written yet"
            continue
        notes[name] = ("ok: " if ok else "FAIL: ") + detail
        if not ok:
            passed = False
            failed.append(name)
    return passed, notes, failed


def run_one(version: agents.Version, case: str, path: Path, model: Any) -> RunResult:
    run = run_incident(agents.harness(version), path, model=model, max_requests=25, use_memory=False)
    failed = [] if run.evaluation is None else [check.name for check in run.evaluation.checks if not check.passed]
    report = run.report.model_dump() if run.report is not None else {}
    ok_trajectory, notes, failed_trajectory = _check_trajectory(run, trajectory_checks())
    actions = [f"{record.action} {record.target} -> {record.outcome}" for record in run.sim.executor.audit]
    return RunResult(
        version=version.name, case=case,
        passed=run.error is None and not failed and ok_trajectory,
        failed=failed + [f"trajectory: {name}" for name in failed_trajectory] + ([run.error] if run.error else []),
        tokens=run.extra.get("input_tokens", 0), requests=run.extra.get("requests", 0),
        status=report.get("status", "no report"), summary=report.get("summary", ""), error=run.error,
        trajectory=notes, actions=actions, description=describe(run),
    )


def run_many(jobs: list[tuple[agents.Version, str, Path]], model: Any, workers: int = 6, on_done: Callable[[int, int], None] | None = None) -> list[RunResult]:
    """Run the jobs in parallel (each on its own fresh simulator)."""
    results: list[RunResult] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_one, version, case, path, model) for version, case, path in jobs]
        for done, future in enumerate(as_completed(futures), start=1):
            try:
                results.append(future.result())
            except Exception as error:  # A failed request must not lose the other runs.
                version, case, _ = jobs[futures.index(future)]
                results.append(RunResult(version.name, case, False, [f"run failed: {error}"], 0, 0, "error", "", str(error), description=f"The run failed: {error}"))
            if on_done:
                on_done(done, len(jobs))
    return results


def pass_rate(results: list[RunResult]) -> float:
    return sum(r.passed for r in results) / len(results) if results else 0.0


def pass_table(results: list[RunResult]) -> list[dict[str, Any]]:
    """One row per case, one column per version: 'passes/runs'."""
    names = list(dict.fromkeys(result.version for result in results))
    rows = []
    for case in sorted({result.case for result in results}):
        row: dict[str, Any] = {"Case": case}
        for name in names:
            runs = [result for result in results if result.case == case and result.version == name]
            row[name] = f"{sum(r.passed for r in runs)}/{len(runs)}" if runs else "-"
        rows.append(row)
    total: dict[str, Any] = {"Case": "TOTAL"}
    for name in names:
        runs = [result for result in results if result.version == name]
        tokens = sum(r.tokens for r in runs) // max(1, len(runs))
        total[name] = f"{sum(r.passed for r in runs)}/{len(runs)} · {tokens:,} tokens/run"
    return rows + [total]
