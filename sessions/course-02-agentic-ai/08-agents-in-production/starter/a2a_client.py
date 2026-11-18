"""Exercise 1 — Ask another team's agent to act, through A2A.

The confirmations of batch 10:12 reached settlement late and must be resent. Your team has no tool for that:
settlement's systems belong to the settlement team. Their agent, the "Settlement Agent", speaks A2A (Agent2Agent).
The on-call already approved the resend (a2a.request has the approval reference).

resend(a2a) talks to the Settlement Agent and returns the final Task.

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
- A task that asks you a question is still the same task.

SOLUTION — published after the session. The code below is one good answer, not the only one.
"""

from __future__ import annotations


async def resend(a2a) -> dict:
    # The Agent Card says what the skill needs and how to authenticate
    card = a2a.card()
    skill = next(s for s in card["skills"] if s["id"] == "resend-confirmations")
    a2a.note(f"Skill '{skill['name']}': bearer token, batch, approval, confirm_count, idempotency key; long-running.")
    request = a2a.request
    key = f"{request['incident']}/resend/{request['batch']}"
    # One request, with an idempotency key: sending it again can never resend twice
    task = await a2a.send_message({"role": "ROLE_USER", "parts": [
        {"text": f"Resend {request['batch']} for incident {request['incident']}. Approval: {request['approval_ref']}."},
        {"data": {"idempotency_key": key, "incident": request["incident"], "batch": request["batch"],
                  "approval_ref": request["approval_ref"]}},
    ]}, a2a.token)
    if "error" in task:
        raise RuntimeError(task["error"]["message"])
    # The agent asks for more: answer inside the same task
    for _ in range(3):
        if task["status"]["state"] != "TASK_STATE_INPUT_REQUIRED":
            break
        asked = next((p["data"] for p in task["status"]["message"]["parts"] if "data" in p), {})
        if "confirmations" in asked:
            a2a.note(f"Settlement asks to confirm {asked['confirmations']} confirmations: answering in the same task.")
            answer = {"data": {"confirm_count": asked["confirmations"]}}
        else:
            a2a.note("Settlement asks for the approval: answering in the same task.")
            answer = {"text": f"Approval reference: {request['approval_ref']}."}
        task = await a2a.send_message({"role": "ROLE_USER", "taskId": task["id"], "contextId": task["contextId"],
                                       "parts": [answer]}, a2a.token)
    # A long task: ask for its state, never send the request again
    while task["status"]["state"] in ("TASK_STATE_SUBMITTED", "TASK_STATE_WORKING"):
        await a2a.wait(1)
        task = await a2a.get_task(task["id"], a2a.token)
    # Check the result before trusting it
    receipt = next((p["data"] for art in task.get("artifacts", []) for p in art["parts"] if "data" in p), {})
    if task["status"]["state"] != "TASK_STATE_COMPLETED" or receipt.get("batch") != request["batch"]:
        a2a.note(f"Settlement did not confirm the resend: {task['status']['state']}.")
    else:
        a2a.note(f"Receipt checked: {receipt['batch']} resent at {receipt['sent_at']}.")
    return task
