"""The naive starter of exercise 2, kept for the tests: one monitor for crashed spans, a vague analyst."""

from __future__ import annotations


def error_spans(trace) -> list[str]:
    return [f"{span['name']} failed: {span['error']}" for span in trace.spans if span["status"] == "ERROR"]


MONITORS = [error_spans]

ANALYST_INSTRUCTIONS = """\
You read the trace of an incident handled by a team of AI agents. Say what happened.
"""


def describe(trace) -> str:
    return f"Incident {trace.root['incident']}, handled with a {trace.root['pattern']}. The team reported: {trace.root['reported']}."
