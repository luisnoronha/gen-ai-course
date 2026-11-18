"""The naive starter of exercise 3, kept for the tests: it hands the whole plan to remediation again."""

from __future__ import annotations


async def resume(room, checkpoint: dict) -> None:
    findings = "\n".join(f"- {name}: {text}" for name, text in checkpoint["findings"].items())
    plan = "\n".join(
        f"{step['step']}) {step['action']} {step['target']}" + (f" (already approved: {step['approval_ref']})" if step["approval_ref"] else "")
        for step in checkpoint["plan"]
    )
    await room.ask("remediation", f"{checkpoint['brief']}\n\nFindings:\n{findings}\n\nCarry out this plan:\n{plan}")
