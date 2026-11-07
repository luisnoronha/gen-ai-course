"""Exercise 2 — Decide whether to adopt a new version.

The lab gives you, for each case, how many runs passed with the current version (baseline) and with the
proposed one (candidate). Write decide(): it returns adopt=True, adopt=False, or adopt=None when the
evidence is not enough to decide. Always give the reasons.

Your rule must handle at least:
- too few runs: one run per case shows luck, not reliability;
- a regression: a case that the baseline passes reliably and the candidate now fails sometimes;
- a gain: cases the candidate passes more often, or a clearly lower cost with no regression.

The lab shows your decision under the comparison table. Compare B with A, then your C with A.

Hints:
- Compare pass rates (passes / runs), not raw counts: the versions may have different numbers of runs.
- Decide what "reliably" means for you and write it as a constant.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CaseComparison:
    case: str
    baseline_passes: int
    baseline_runs: int
    candidate_passes: int
    candidate_runs: int


@dataclass
class Decision:
    adopt: bool | None
    reasons: list[str] = field(default_factory=list)


def decide(cases: list[CaseComparison], baseline_tokens: float, candidate_tokens: float) -> Decision:
    """baseline_tokens and candidate_tokens: average input tokens per run."""
    raise NotImplementedError
