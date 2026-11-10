"""The parts of the improvement loop that think: the students' starter/improver.py, or a simple default.

Each function returns (result, origin) with origin "yours" or "default", so the app can show who did what.
A NotImplementedError means "not written yet": the default is used. Any other error stops the loop and is shown.
"""

from __future__ import annotations

import importlib.util
import sys
from typing import Any

from pydantic_ai import Agent

import agents
from models import Proposal, Review

DEFAULT_PROPOSER = """\
You improve the instructions of an incident agent. You receive its current instructions,
the critic's reviews of its last runs, and what you remember from earlier attempts.
Propose ONE change. Return the change in one line, and the complete new instructions.
"""


def _improver():
    spec = importlib.util.spec_from_file_location("s06_improver", agents.STARTER / "improver.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["s06_improver"] = module
    spec.loader.exec_module(module)
    return module


def _yours(name: str, *args: Any) -> tuple[bool, Any]:
    try:
        return True, getattr(_improver(), name)(*args)
    except NotImplementedError:
        return False, None


def describe(run: Any) -> tuple[str, str]:
    """What the critic sees about one run. Default: only the agent's own words."""
    mine, text = _yours("describe_run", run)
    if mine:
        return text, "yours"
    report = run.report
    if report is None:
        return f"The run ended without a report ({run.error}).", "default"
    return f"Status reported by the agent: {report.status}\nSummary: {report.summary}", "default"


def critic_agent(model: Any, instructions: str) -> tuple[Agent, str]:
    mine, agent = _yours("build_critic", model, instructions)
    if mine:
        return agent, "yours"
    return Agent(model, output_type=Review, instructions=instructions), "default"


def proposer_agent(model: Any) -> tuple[Agent, str]:
    mine, agent = _yours("build_proposer", model)
    if mine:
        return agent, "yours"
    return Agent(model, output_type=Proposal, instructions=DEFAULT_PROPOSER), "default"


def proposer_message(instructions: str, verify_recovery: bool, reviews: list[tuple[str, Review]], memory: str) -> tuple[str, str]:
    mine, text = _yours("proposer_message", instructions, verify_recovery, reviews, memory)
    if mine:
        return text, "yours"
    lines = [f"- {case}: {review.problem}" for case, review in reviews if review.score <= 3]
    return (f"CURRENT INSTRUCTIONS:\n{instructions}\n\nREVIEWS:\n" + ("\n".join(dict.fromkeys(lines)) or "- none")
            + f"\n\nMEMORY:\n{memory}"), "default"


def lesson(attempt: Any) -> tuple[str | None, str]:
    mine, line = _yours("lesson", attempt)
    return (line, "yours") if mine else (None, "none")


def recall(lessons: list[str]) -> tuple[str, str]:
    mine, text = _yours("recall", lessons)
    return (text, "yours") if mine else ("(no memory: lesson() and recall() are not written yet)", "none")
