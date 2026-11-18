"""The naive starter of exercise 1, kept for the tests: it answers in the task, then sends the request again."""

from __future__ import annotations


async def resend(a2a) -> dict:
    request = a2a.request
    text = f"Please resend {request['batch']} for incident {request['incident']}. Approval: {request['approval_ref']}."
    task: dict = {}
    for _ in range(3):
        task = await a2a.send_message({"role": "ROLE_USER", "parts": [{"text": text}]}, a2a.token)
        if task.get("status", {}).get("state") == "TASK_STATE_INPUT_REQUIRED":
            asked = next((p["data"] for p in task["status"]["message"]["parts"] if "data" in p), {})
            task = await a2a.send_message({"role": "ROLE_USER", "taskId": task["id"],
                                           "parts": [{"data": {"confirm_count": asked.get("confirmations")}}]}, a2a.token)
        if task.get("status", {}).get("state") == "TASK_STATE_COMPLETED":
            return task
        await a2a.wait(1)
    return task
