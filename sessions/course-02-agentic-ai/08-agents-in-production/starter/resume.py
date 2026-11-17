"""Exercise 3 — Resume after a crash, without repeating what was done.

The lab runs the first half of incident INC-2 and saves a checkpoint after each step:
findings → plan → step 1 (fail over to site C) → step 2 (resend the delayed confirmations to settlement).
Then the process crashes. resume(room, checkpoint) is what the next shift runs.

The resume below works, but it is naive: it trusts the checkpoint and hands the whole plan to remediation again.
Run scenario A and look at the result. Then make it safe.

What a good resume must do:
- never repeat an effect that already happened (resending the confirmations twice charges members twice);
- not trust "status" in the checkpoint blindly: the crash can happen between doing a step and saving that it was done;
- check every approval it reuses: time passes during a crash (scenario B);
- finish the work that is really left, with the agents, and confirm the result.

What you can use (lab/room.py has the details):
- checkpoint["plan"]: the steps, each with action, target, key (its idempotency key), status, approval_ref
- room.history(): every action the systems really ran, with its key. It survives the crash.
- room.approval_status(ref): is an approval still valid now?
- await room.ask("remediation" | "reviewer", message): give a task to an agent
- room.note(text): show on the board what your code decided

Hints:
- Where is the truth after a crash: in the checkpoint, in the systems, or in the agent's memory?
- An idempotency key is only useful if the retry sends the same key.
- Remediation does exactly what you ask. If you ask for everything, it does everything.
"""

from __future__ import annotations


async def resume(room, checkpoint: dict) -> None:
    findings = "\n".join(f"- {name}: {text}" for name, text in checkpoint["findings"].items())
    plan = "\n".join(
        f"{step['step']}) {step['action']} {step['target']}" + (f" (already approved: {step['approval_ref']})" if step["approval_ref"] else "")
        for step in checkpoint["plan"]
    )
    await room.ask("remediation", f"{checkpoint['brief']}\n\nFindings:\n{findings}\n\nCarry out this plan:\n{plan}")
