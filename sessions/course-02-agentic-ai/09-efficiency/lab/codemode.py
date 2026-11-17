"""Trainer demo: "code mode". The same check, done two ways.

- Tools: the agent calls read_metrics and check_link one by one. Every result goes back into its context.
- Code: the agent writes one short Python script that calls the same functions, runs it in a sandbox, and reads
  only what the script prints.

The sandbox here: no imports, a short list of builtins, only the three tool functions, 5 seconds, 4 000 characters
of output. A real one isolates a process or a container; the idea is the same.
"""

from __future__ import annotations

import asyncio
import io
import threading
import time
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from typing import Any

from common import HERE, patient
from pydantic_ai import Agent

from meridian.simulator import Simulator
from meridian.tools import MeridianTools

TASK = ("Check the health of Meridian Exchange now: the latency and error rate of every component "
        "(order-gateway, matching-engine, market-data, settlement, reference-db), and every link from order-gateway "
        "to the other four. Then list what is unhealthy, with the numbers.")
COMPONENTS = ["order-gateway", "matching-engine", "market-data", "settlement", "reference-db"]
SAFE = ("print", "len", "range", "sorted", "min", "max", "sum", "round", "dict", "list", "str", "int", "float",
        "enumerate", "zip", "abs", "any", "all", "isinstance", "set", "tuple", "bool")
TIMEOUT = 5.0
MAX_OUTPUT = 4000


class Systems:
    def __init__(self) -> None:
        self.tools = MeridianTools(Simulator(HERE / "incidents" / "incident.yaml"), actor="demo")
        self.lock = threading.Lock()

    def read_metrics(self, component: str) -> dict[str, Any]:
        """Latest latency_ms and error_rate of a component."""
        with self.lock:
            readings = self.tools.read_metrics(component, 1)
        if "error" in readings:
            return readings
        last = readings["readings"][-1]
        return {"component": component, "latency_ms": last["latency_ms"], "error_rate": last["error_rate"]}

    def check_link(self, source: str, target: str) -> dict[str, Any]:
        """State of a link: up, degraded or down."""
        with self.lock:
            return self.tools.check_link(source, target)


def sandbox(code: str, systems: Systems) -> str:
    """Run the agent's script with only the tool functions and a few builtins."""
    import builtins

    scope = {"__builtins__": {name: getattr(builtins, name) for name in SAFE},
             "read_metrics": systems.read_metrics, "check_link": systems.check_link}
    out, box = io.StringIO(), {}

    def run() -> None:
        try:
            with redirect_stdout(out):
                exec(code, scope)  # noqa: S102 - the point of the demo; restricted scope above
        except Exception as error:  # noqa: BLE001 - the agent reads the error and fixes its script
            box["error"] = f"{type(error).__name__}: {error}"

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(TIMEOUT)
    if worker.is_alive():
        return f"Stopped: the script ran more than {TIMEOUT:.0f} seconds."
    text = out.getvalue()[:MAX_OUTPUT]
    return text + (f"\n{box['error']}" if "error" in box else "")


@dataclass
class Duel:
    model: Any
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    scripts: list[str] = field(default_factory=list)
    error: str | None = None
    running: bool = False

    def start(self) -> threading.Thread:
        self.running = True
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        return thread

    def _run(self) -> None:
        try:
            asyncio.run(self._main())
        except Exception as error:  # noqa: BLE001 - keep the page when a run fails
            self.error = f"{type(error).__name__}: {error}"
        finally:
            self.running = False

    async def _main(self) -> None:
        model = patient(self.model)
        systems = Systems()
        tools_agent = Agent(model, name="tools", instructions="You check the health of a stock exchange with your tools.",
                            tools=[systems.read_metrics, systems.check_link])

        def run_python(code: str) -> str:
            """Run a Python script. It can call read_metrics(component) and check_link(source, target), and must print
            what you need to read. No imports."""
            self.scripts.append(code)
            return sandbox(code, systems)

        code_agent = Agent(model, name="code", tools=[run_python],
                           instructions=("You check the health of a stock exchange. Write ONE Python script that calls the "
                                         "functions read_metrics(component) and check_link(source, target) for everything you need, "
                                         "and prints only a compact summary. Run it with run_python, then answer."))
        for name, agent in (("Tools, one by one", tools_agent), ("Code mode", code_agent)):
            began = time.monotonic()
            result = await agent.run(TASK)
            usage = result.usage
            self.results[name] = {"Model calls": usage.requests, "Tool calls": usage.tool_calls,
                                  "Tokens": (usage.input_tokens or 0) + (usage.output_tokens or 0),
                                  "Seconds": round(time.monotonic() - began, 1), "answer": str(result.output)}


def blocked_example(systems: Systems | None = None) -> str:
    """What the sandbox says to a script that tries to leave it."""
    return sandbox("import os\nprint(os.listdir('/'))", systems or Systems())

