"""Hooks: code the harness runs at fixed points of every agent run, whatever the model decides.

PydanticAI calls them for us (Agent(..., capabilities=[HOOKS])):
- before_tool_execute: before a tool runs. Decides if the call may happen (permissions, evidence)
  and can block it without running the tool.
- after_tool_execute:  after a tool runs. Records what happened, and passes what the model is
  about to read through the guardrails.
- after_run:           when the agent has finished. Checks the final answer.

Each control is switched on and off in the app (lab.on("...")).
"""

from __future__ import annotations

import dataclasses
from typing import Any

from pydantic_ai.capabilities import Hooks
from pydantic_ai.exceptions import SkipToolExecution

import guardrails

ACTIONS = ("restart_instance", "restart_service")


# Rules used by the hooks -----------------------------------------------------------------------


def permission_denial(role: str, action: str, critical: bool) -> str | None:
    """Who may do what. An approval does not change it."""
    if role == "on-call":
        return None  # On-call may act; critical restarts still need an approval (the executor checks it).
    if role == "first-line" and action == "restart_instance" and not critical:
        return None
    return f"{role} may only restart a noncritical instance. An approval does not grant this permission."


def evidence_denial(state: Any, action: str, target: str) -> str | None:
    """The live metrics must justify the restart, whatever the agent read."""
    if action == "restart_instance":
        _, instance = state.instance(target)
        if instance.status == "running" and (instance.memory_pct > 90 or instance.latency_ms > 50):
            return None
        return f"{target} has no restart justification (memory {instance.memory_pct:.0f}%, latency {instance.latency_ms:.0f} ms)."
    component = state.component(target)
    if component.latency_ms > 50 or component.error_rate > 0.05:
        return None
    return f"{target} is healthy (latency {component.latency_ms:.0f} ms, errors {component.error_rate:.1%}). The log is not evidence of a fault."


def _target(args: dict[str, Any]) -> str:
    return args.get("instance_id") or args.get("component") or ""


# The hooks -----------------------------------------------------------------------------------


async def before_tool_execute(ctx, *, call, tool_def, args):
    lab = ctx.deps
    name = call.tool_name
    reason = None
    if name in ACTIONS:
        target = _target(args)
        try:
            critical = lab.sim.executor._target_component(name, target).critical
        except (KeyError, ValueError):
            critical = False
        if lab.on("permissions"):
            reason = permission_denial(lab.acting_as["role"], name, critical)
        if reason is None and lab.on("evidence"):
            try:
                reason = evidence_denial(lab.sim.state, name, target)
            except KeyError:
                reason = None  # unknown target: the executor rejects it
    if name == "send_message" and lab.on("check_messages"):
        reason = guardrails.message_denial(args["channel"], args["text"])
    if reason:
        lab.record_action(name, _target(args) or args.get("channel", ""), args.get("confirmation_ref"), "blocked", reason)
        lab.log(f"Hook blocked {name}", reason)
        raise SkipToolExecution({"status": "blocked", "reason": reason})
    return args


async def after_tool_execute(ctx, *, call, tool_def, args, result):
    lab = ctx.deps
    name = call.tool_name
    if name == "read_logs":
        lines = [dict(line) for line in result.get("lines", [])]
        if lab.on("mask_personal_data"):
            for line in lines:
                line["message"] = guardrails.mask_personal_data(line["message"])
            lab.log("Guardrail masked personal data", f"{len(lines)} log lines")
        if lab.on("instruction_guardrail"):
            flagged = await guardrails.find_instructions([line["message"] for line in lines], lab.model, lab.guardrail_prompt)
            for index in sorted(flagged):
                lab.log("Guardrail removed an instruction", lines[index]["message"])
                lines[index]["message"] = "[removed: this log contained an instruction]"
        result = {**result, "lines": lines}
        lab.reads.append({"component": args["component"], "lines": [dict(line) for line in lines]})
    if name in ACTIONS or name == "send_message":
        target = _target(args) or args.get("channel", "")
        lab.record_action(name, target, args.get("confirmation_ref"), result.get("status", ""), result.get("reason", result.get("detail", "")))
    lab.log(f"{name} {dict(args)}", result)
    return result


async def after_run(ctx, *, result):
    lab = ctx.deps
    if lab.on("output_guardrail") and isinstance(result.output, str):
        cleaned = guardrails.mask_personal_data(result.output)
        if cleaned != result.output:
            lab.log("Guardrail masked personal data in the final answer", "")
            return dataclasses.replace(result, output=cleaned)
    return result


HOOKS = Hooks(before_tool_execute=before_tool_execute, after_tool_execute=after_tool_execute, after_run=after_run)
