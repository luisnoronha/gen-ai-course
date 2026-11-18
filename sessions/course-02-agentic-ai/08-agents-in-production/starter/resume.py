"""Exercise 3 — Resume after a crash, without repeating what was done.

The lab runs the first half of incident INC-2 and saves a checkpoint after each step:
findings → plan → step 1 (fail over to site C) → step 2 (resend the delayed confirmations to settlement).
Then the process crashes. resume(room, checkpoint) is what the next shift runs.

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

SOLUTION — published after the session. The code below is one good answer, not the only one.
"""

from __future__ import annotations


async def resume(room, checkpoint: dict) -> None:
    # What really ran, by idempotency key: the crash may have hit between doing a step and saving it
    done = {effect["key"] for effect in room.history()}
    tasks = []
    for step in checkpoint["plan"]:
        if step["key"] in done:
            room.note(f"Step {step['step']} ({step['action']}) already ran: it is in the systems' history. Skip it.")
            continue
        # Time passed during the crash: an approval from before may not hold any more
        ref = step["approval_ref"]
        if ref and not room.approval_status(ref)["valid"]:
            room.note(f"Step {step['step']}: approval {ref} is no longer valid. Ask the on-call again.")
            ref = None
        tasks.append(f"- {step['action']} {step['target']}, idempotency_key={step['key']}"
                     + (f", approval_ref={ref}" if ref else ", no approval yet: ask the on-call"))
    if tasks:
        findings = "\n".join(f"- {name}: {text}" for name, text in checkpoint["findings"].items())
        await room.ask("remediation", f"{checkpoint['brief']}\n\nFindings:\n{findings}\n\n"
                                      "Other steps are already done. Do only these, with exactly these keys:\n" + "\n".join(tasks))
    else:
        room.note("Nothing left to do: every step is in the systems' history.")
    # Confirm with someone who did not do the work
    await room.ask("reviewer", "The incident team resumed after a crash. Is the incident over, and did any action run twice?")
