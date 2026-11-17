"""Exercise 2: find the cause in the traces, and watch the agents in production.

A trace is the list of OpenTelemetry spans of one incident run (see lab/record.py). Each span has the GenAI attributes:
gen_ai.operation.name (invoke_agent, chat, execute_tool), gen_ai.agent.name, gen_ai.request.model,
gen_ai.usage.input_tokens / output_tokens, gen_ai.tool.name, gen_ai.tool.call.arguments / result.

What your monitors get (a Trace):
- trace.root            the incident span: incident, pattern, reported, recovered, gateway
- trace.spans           every span (name, operation, agent, tool, model, input_tokens, output_tokens, start_ms, end_ms, attributes)
- trace.agents()        per agent: model_calls, tool_calls, input_tokens, output_tokens
- trace.tool_calls()    every tool call: agent, tool, arguments, result
- trace.cost_usd()      what the run cost, from the tokens and the model's price
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic_ai import Agent
from room import HERE, load_starter, patient

TRACES = HERE / "traces"
LIVE = HERE / ".runs"
PRICES = {"gpt-4.1": (2.00, 8.00), "gpt-4.1-mini": (0.40, 1.60), "gpt-4.1-nano": (0.10, 0.40)}  # USD per 1M tokens (in, out)


class Trace:
    def __init__(self, data: dict[str, Any], name: str) -> None:
        self.name, self.title, self.source = name, data["title"], data["source"]
        self.spans = [_span(s) for s in data["spans"]]
        root = next(s for s in self.spans if s["parent_id"] is None)
        self.root = {key.removeprefix("meridian."): value for key, value in root["attributes"].items()}
        if isinstance(self.root.get("gateway"), str):
            self.root["gateway"] = json.loads(self.root["gateway"])

    def agents(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for span in self.spans:
            if not span["agent"]:
                continue
            row = out.setdefault(span["agent"], {"model_calls": 0, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0})
            row["model_calls"] += span["operation"] == "chat"
            row["tool_calls"] += span["operation"] == "execute_tool"
            row["input_tokens"] += span["input_tokens"]
            row["output_tokens"] += span["output_tokens"]
        return out

    def tool_calls(self) -> list[dict[str, Any]]:
        return [{"agent": s["agent"], "tool": s["tool"], "arguments": s["attributes"].get("gen_ai.tool.call.arguments", ""),
                 "result": s["attributes"].get("gen_ai.tool.call.result", ""), "start_ms": s["start_ms"]}
                for s in self.spans if s["operation"] == "execute_tool"]

    def cost_usd(self) -> float:
        total = 0.0
        for span in self.spans:
            price_in, price_out = PRICES.get(span["model"] or "", PRICES["gpt-4.1-mini"])
            total += (span["input_tokens"] * price_in + span["output_tokens"] * price_out) / 1e6
        return round(total, 5)


def _span(raw: dict[str, Any]) -> dict[str, Any]:
    a = raw["attributes"]
    return {**raw, "operation": a.get("gen_ai.operation.name"), "agent": a.get("gen_ai.agent.name"), "tool": a.get("gen_ai.tool.name"),
            "model": a.get("gen_ai.request.model"), "input_tokens": int(a.get("gen_ai.usage.input_tokens", 0)),
            "output_tokens": int(a.get("gen_ai.usage.output_tokens", 0))}


def recorded() -> list[tuple[Trace, dict[str, Any]]]:
    """The four recorded traces, with what really happened (shown after the analyst answers), then the live ones."""
    index = json.loads((TRACES / "index.json").read_text(encoding="utf-8"))
    out = [(Trace(json.loads((TRACES / item["file"]).read_text(encoding="utf-8")), item["file"]), item) for item in index]
    for path in sorted(LIVE.glob("live-*.json")) if LIVE.exists() else []:
        trace = Trace(json.loads(path.read_text(encoding="utf-8")), path.name)
        trace.title = f"{trace.title} · {path.stem.removeprefix('live-')}"  # two live runs never share a title
        out.append((trace, {"file": path.name, "title": trace.title, "should_fire": None,
                            "what_happened": "A live run: nobody knows yet. Read the trace."}))
    return out


def waterfall_rows(trace: Trace) -> list[dict[str, Any]]:
    """The spans in order, with their depth, for the board's waterfall."""
    depth = {}
    rows = []
    for span in sorted(trace.spans, key=lambda s: s["start_ms"]):
        depth[span["span_id"]] = depth.get(span["parent_id"], -1) + 1
        op = span["operation"] or "incident"
        if op == "chat":
            label = f"chat {span['model']} · {span['input_tokens'] + span['output_tokens']:,} tokens"
        elif op == "execute_tool":
            label = f"{span['tool']}({_short(span['attributes'].get('gen_ai.tool.call.arguments', ''), 60)})"
        elif op == "invoke_agent":
            label = f"agent {span['agent']}"
        else:
            label = span["name"]
        rows.append({"label": label, "depth": depth[span["span_id"]], "start": span["start_ms"], "end": span["end_ms"], "kind": op,
                     "detail": _short(span["attributes"].get("gen_ai.tool.call.result", ""), 200), "error": span["status"] == "ERROR",
                     "span": {"name": span["name"], "trace_id": span.get("trace_id"), "span_id": span["span_id"],
                              "parent_span_id": span["parent_id"], "start_ms": span["start_ms"], "end_ms": span["end_ms"],
                              "status": span["status"], "attributes": span["attributes"]}})
    return rows


def _short(text: Any, n: int) -> str:
    text = str(text).replace("\n", " ")
    return text if len(text) <= n else text[:n] + "…"


# Running your monitors and your analyst ---------------------------------------------------------------


@dataclass
class Review:
    model: Any
    rows: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    running: bool = False
    seconds: float = 0.0
    calls: int = 0

    def start(self) -> threading.Thread:
        self.running = True
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        return thread

    def _run(self) -> None:
        began = time.monotonic()
        try:
            asyncio.run(self._main())
        except NotImplementedError:
            self.error = "Not written yet: starter/monitors.py. Write it, save the file and click Run again."
        except Exception as error:  # noqa: BLE001 - keep the page when a run fails
            self.error = f"{type(error).__name__}: {error}"
        finally:
            self.seconds = round(time.monotonic() - began, 1)
            self.running = False

    async def _main(self) -> None:
        mine = load_starter("monitors")
        analyst = Agent(patient(self.model), instructions=mine.ANALYST_INSTRUCTIONS, name="trace-analyst", retries=3)
        traces = recorded()

        def watch(trace: Trace) -> list[str]:
            alerts = []
            for monitor in mine.MONITORS:
                try:
                    alerts += [f"{monitor.__name__}: {alert}" for alert in monitor(trace)]
                except Exception as error:  # say which monitor broke, on which trace
                    raise RuntimeError(f"your monitor {monitor.__name__}() failed on '{trace.title}': {type(error).__name__}: {error}") from error
            return alerts

        async def review(trace: Trace, info: dict[str, Any]) -> dict[str, Any]:
            alerts = watch(trace)
            answer = (await analyst.run(mine.describe(trace))).output
            return {"trace": trace.title, "should_fire": info["should_fire"], "alerts": alerts, "analyst": answer,
                    "what_happened": info["what_happened"]}

        self.rows = list(await asyncio.gather(*(review(t, i) for t, i in traces)))
        self.calls = len(traces)

    def verdict(self) -> list[tuple[bool, str]]:
        checks = []
        for row in self.rows:
            if row["should_fire"] is None:
                continue
            fired = bool(row["alerts"])
            if row["should_fire"]:
                checks.append((fired, f"{row['trace']}: " + ("your monitors caught it" if fired else "a problem, and no monitor fired")))
            else:
                checks.append((not fired, f"{row['trace']}: " + ("healthy, and no monitor fired" if not fired else "healthy, but a monitor fired (false alarm)")))
        return checks


def record_live(incident: str = "INC-2", pattern: str = "pipeline") -> Path:
    """Run the session 7 team with the real model, in its own process, and save the trace."""
    LIVE.mkdir(exist_ok=True)
    out = LIVE / f"live-{time.strftime('%H%M%S')}.json"
    done = subprocess.run([sys.executable, str(HERE / "record.py"), "--out", str(out), "--incident", incident, "--pattern", pattern],
                          cwd=HERE.parents[3], capture_output=True, text=True, timeout=300, check=False)
    if done.returncode != 0:
        lines = (done.stderr or done.stdout).strip().splitlines()
        raise RuntimeError(lines[-1] if lines else f"record.py stopped with code {done.returncode}")
    return out
