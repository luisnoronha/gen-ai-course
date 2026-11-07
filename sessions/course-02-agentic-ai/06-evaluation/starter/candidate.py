"""Exercise 3 — Propose version C.

Version B is cheaper and faster than A, and wins on some cases. It also fails cases that A passes.
Write the instructions of a version C that keeps B's gains without its regressions, then measure it in the
lab against A, with the same cases and several repetitions. Keep the change only if decide() agrees.

What you can change:
- INSTRUCTIONS: the agent's instructions (same tools and report as A and B; see lab/agents.py);
- VERIFY_RECOVERY: True adds A's check in code: "resolved" only if the last 3 readings are healthy.

Hints:
- Look at the failed checks of each version first. Change one thing at a time.
- A cheaper version that fails a case once in five is not cheaper: count the failures as well.
"""

DESCRIPTION = "Version C: describe your change in one line."

INSTRUCTIONS = """\
"""

VERIFY_RECOVERY = False
