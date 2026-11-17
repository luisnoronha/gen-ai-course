"""Trainer demo: two workers share a queue of incidents. No model: the point is where the state lives.

- "memory": each worker keeps in its own memory which incidents it took. Both take the same ones.
- "shared": a shared store gives each incident to one worker at a time (a lease that expires).
- crash: worker 1 dies after acting on INC-2 and before saving that it finished. With a lease, worker 2 takes
  INC-2 over when the lease expires, and checks the systems' history before acting again.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Literal

QUEUE = [
    ("INC-2", "resend_confirmations batch-10:12"),
    ("INC-3", "restart_instance market-data-2"),
    ("INC-4", "purge_cache member-portal"),
]
STEP = 0.7  # seconds per step
LEASE = 2.5  # seconds a lease lasts without renewal


@dataclass
class Fleet:
    mode: Literal["memory", "shared"]
    crash: bool = False
    cards: dict[str, dict[str, str]] = field(default_factory=dict)
    feed: list[dict[str, str]] = field(default_factory=list)
    effects: list[dict[str, str]] = field(default_factory=list)  # the systems' history
    leases: dict[str, dict[str, Any]] = field(default_factory=dict)  # the shared store
    running: bool = False
    error: str | None = None
    seconds: float = 0.0

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._began = time.monotonic()

    def post(self, sender: str, to: str, text: str, kind: str = "message") -> None:
        self.feed.append({"time": f"+{time.monotonic() - self._began:4.1f}s", "from": sender, "to": to, "text": text, "kind": kind})

    def set_card(self, name: str, status: str, activity: str = "") -> None:
        self.cards[name] = {"status": status, "activity": activity}

    # The shared store ----------------------------------------------------------------------------

    def _take(self, worker: str, incident: str) -> bool:
        with self._lock:
            lease = self.leases.get(incident)
            now = time.monotonic()
            if lease and (lease["done"] or (lease["owner"] != worker and lease["until"] > now)):
                return False
            took_over = lease is not None and lease["owner"] != worker
            self.leases[incident] = {"owner": worker, "until": now + LEASE, "done": False}
        self.post(worker, "store", f"Lease on {incident}" + (" (the previous lease expired: taking it over)" if took_over else ""), "checkpoint")
        self._show_store()
        return True

    def _finish(self, worker: str, incident: str) -> None:
        with self._lock:
            self.leases[incident]["done"] = True
        self.post(worker, "store", f"{incident} finished", "checkpoint")
        self._show_store()

    def _show_store(self) -> None:
        lines = [f"{i}: {'done' if l['done'] else l['owner']}" for i, l in sorted(self.leases.items())]
        self.set_card("store", "done", "\n".join(lines) or "empty")

    # The workers -----------------------------------------------------------------------------------

    def _act(self, worker: str, incident: str, action: str, check_history: bool = False) -> None:
        """Run the action. When taking over someone else's incident, read the systems' history first."""
        with self._lock:
            if check_history and any(e["incident"] == incident for e in self.effects):
                skip = True
            else:
                skip = False
                self.effects.append({"incident": incident, "action": action, "worker": worker})
        if skip:
            self.post(worker, "systems", f"{incident}: history says '{action}' already ran. Skip it.", "tool")
        else:
            self.post(worker, "systems", f"{incident}: {action}", "action")

    def _worker(self, worker: str) -> None:
        taken: set[str] = set()  # what this worker remembers, in its own memory
        for incident, action in QUEUE:
            if self.mode == "memory":
                if incident in taken:
                    continue
                taken.add(incident)
            elif not self._take(worker, incident):
                self.post(worker, "store", f"{incident} belongs to another worker: next.", "tool")
                continue
            self.set_card(worker, "working", f"{incident}: investigating")
            time.sleep(STEP)
            self.set_card(worker, "working", f"{incident}: {action}")
            self._act(worker, incident, action)
            time.sleep(STEP)
            if self.crash and worker == "worker-1" and incident == "INC-2":
                self.set_card(worker, "error", "Crashed after acting on INC-2, before saving that it finished.")
                self.post(worker, "board", "CRASH: worker 1 died.", "crash")
                return
            if self.mode == "shared":
                self._finish(worker, incident)
        self.set_card(worker, "done", "Queue empty.")

    def _rescue(self) -> None:
        """With a lease, a crashed worker's incident goes back to the queue when the lease expires."""
        if self.mode != "shared" or not self.crash:
            return
        time.sleep(LEASE + 0.5)
        for incident, action in QUEUE:
            if self._take("worker-2", incident):
                self.set_card("worker-2", "working", f"{incident}: taken over")
                time.sleep(STEP)
                self._act("worker-2", incident, action, check_history=True)
                self._finish("worker-2", incident)
        self.set_card("worker-2", "done", "Queue empty.")

    def start(self) -> threading.Thread:
        self.running = True
        self.set_card("store", "done" if self.mode == "shared" else "unused", "empty" if self.mode == "shared" else "")
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        return thread

    def _run(self) -> None:
        try:
            workers = [threading.Thread(target=self._worker, args=(w,)) for w in ("worker-1", "worker-2")]
            for w in workers:
                w.start()
                time.sleep(0.15)
            for w in workers:
                w.join()
            self._rescue()
        except Exception as error:  # noqa: BLE001 - keep the board when a run fails
            self.error = f"{type(error).__name__}: {error}"
        finally:
            self.seconds = round(time.monotonic() - self._began, 1)
            self.running = False

    def verdict(self) -> list[tuple[bool, str]]:
        checks = []
        for incident, action in QUEUE:
            n = sum(e["incident"] == incident for e in self.effects)
            checks.append((n == 1, f"{incident} · {action}: ran {n}×"))
        return checks
