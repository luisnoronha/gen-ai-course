"""Exercise 1 — Ask another team's agent to act, through A2A.

The confirmations of batch 10:12 reached settlement late and must be resent. Your team has no tool for that:
settlement's systems belong to the settlement team. Their agent, the "Settlement Agent", speaks A2A (Agent2Agent).
The on-call already approved the resend (a2a.request has the approval reference).

resend(a2a) talks to the Settlement Agent and returns the final Task.

The client below works, but it is naive. It answers settlement's question correctly (inside the same task), but
because settlement is slow, it then sends the whole request again. Run it and look at the result. Then write a client
that holds up.

What a good client must do:
- read the Agent Card first: what the skill needs, and how to authenticate;
- send the request once, with what the skill asks for;
- answer the agent inside the same task if it needs more from you (TASK_STATE_INPUT_REQUIRED);
- wait for a long task by asking for its state (GetTask), never by sending the request again;
- check the result before returning it.

What you can use (lab/a2a.py has the details): a2a.card(), await a2a.send_message(message, token),
await a2a.get_task(task_id, token), a2a.token, a2a.request, await a2a.wait(seconds), a2a.note(text).
A message (A2A v1.0): {"role": "ROLE_USER", "parts": [{"text": "..."}, {"data": {...}}], "taskId"?: "...", "contextId"?: "..."}

Hints:
- Read every field of the skill's description in the card. One sentence in it is the whole exercise.
- TASK_STATE_WORKING is not TASK_STATE_FAILED. What is the difference between sending again and asking again?
- A task that asks you a question is still the same task. The naive client already gets this part right.
"""

from __future__ import annotations


async def resend(a2a) -> dict:
    request = a2a.request
    text = f"Please resend {request['batch']} for incident {request['incident']}. Approval: {request['approval_ref']}."
    task: dict = {}
    for _ in range(3):
        task = await a2a.send_message({"role": "ROLE_USER", "parts": [{"text": text}]}, a2a.token)
        if task.get("status", {}).get("state") == "TASK_STATE_INPUT_REQUIRED":
            # settlement asks to confirm how many confirmations it will resend: answer inside the same task
            asked = next((p["data"] for p in task["status"]["message"]["parts"] if "data" in p), {})
            task = await a2a.send_message({"role": "ROLE_USER", "taskId": task["id"],
                                           "parts": [{"data": {"confirm_count": asked.get("confirmations")}}]}, a2a.token)
        if task.get("status", {}).get("state") == "TASK_STATE_COMPLETED":
            return task
        await a2a.wait(1)  # settlement is slow: send the request again
    return task
