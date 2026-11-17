"""Exercise 1: talk to another team's agent through A2A (Agent2Agent protocol).

The settlement team runs its own agent. Your team cannot call settlement's systems: you send the agent a task over A2A.
This is an in-process version of A2A v1.0 (JSON-RPC binding): the same Agent Card, methods (SendMessage, GetTask),
message parts and task states as the spec. No network, so the lab is the same for everybody.
Every call carries the header A2A-Version: 1.0, and asks for an immediate answer (returnImmediately), so you see each state.

What your client gets (the `a2a` object):
- a2a.card()                                  the Settlement Agent's Agent Card (skills, security, ...)
- await a2a.send_message(message, token)      JSON-RPC SendMessage; its result is {"task": ...}: returns that Task, or an {"error": ...}
- await a2a.get_task(task_id, token)          JSON-RPC GetTask; returns the Task as it is now
- a2a.token                                   your team's bearer token for settlement
- a2a.request                                 what you need: {"incident": ..., "batch": ..., "approval_ref": ...}
- await a2a.wait(seconds)                     wait before asking again
- a2a.note(text)                              show on the board what your code decided

A Message: {"role": "ROLE_USER", "parts": [{"text": "..."}, {"data": {...}}], "taskId"?: ..., "contextId"?: ...}
A Task: {"id", "contextId", "status": {"state", "message"}, "artifacts", ...}
States: TASK_STATE_SUBMITTED, TASK_STATE_WORKING, TASK_STATE_INPUT_REQUIRED, TASK_STATE_COMPLETED, TASK_STATE_FAILED,
TASK_STATE_REJECTED, TASK_STATE_CANCELED, TASK_STATE_AUTH_REQUIRED.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent
from room import load_starter, patient
from world import BATCH, World

TOKEN = "stl-7f3a-incident-team"
CONFIRMATIONS, MEMBERS = 1240, 38  # what batch-10:12 holds: settlement asks the client to confirm this number
WORK_SECONDS = 3.0  # how long settlement takes to resend a batch
MAX_SECONDS = 60

# Task states (A2A v1.0, ProtoJSON enum names)
SUBMITTED, WORKING, INPUT_REQUIRED = "TASK_STATE_SUBMITTED", "TASK_STATE_WORKING", "TASK_STATE_INPUT_REQUIRED"
COMPLETED, FAILED, REJECTED = "TASK_STATE_COMPLETED", "TASK_STATE_FAILED", "TASK_STATE_REJECTED"

CARD: dict[str, Any] = {
    "name": "Settlement Agent",
    "description": "The settlement team's agent at Meridian Exchange. Handles requests about order confirmations.",
    "supportedInterfaces": [{"url": "https://settlement.meridian.internal/a2a/v1", "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}],
    "version": "2.1.0",
    "provider": {"organization": "Meridian Exchange · Settlement team"},
    "capabilities": {"streaming": False, "pushNotifications": False},
    "securitySchemes": {"bearer": {"httpAuthSecurityScheme": {"scheme": "Bearer", "description": "A team token issued by settlement."}}},
    "securityRequirements": [{"schemes": {"bearer": {"list": []}}}],
    "defaultInputModes": ["text/plain", "application/json"],
    "defaultOutputModes": ["application/json"],
    "skills": [{
        "id": "resend-confirmations",
        "name": "Resend order confirmations",
        "description": ("Resends a delayed batch of order confirmations to settlement. Needs the batch id and the on-call's "
                        "approval reference. Members are charged for every confirmation sent, so before resending the agent asks, "
                        "in the same task, to confirm how many confirmations will go out: reply in that task with a data part "
                        "{\"confirm_count\": N}. Send an idempotency_key in a data part: a key settlement has seen is never sent twice. "
                        "Long-running: the task stays TASK_STATE_WORKING for a few seconds; poll it with GetTask. "
                        "Every SendMessage without a taskId or a known idempotency_key starts a NEW resend."),
        "tags": ["settlement", "confirmations", "resend"],
        "examples": ["Resend batch-10:12 for incident INC-2. Approval: APR-001."],
        "inputModes": ["text/plain", "application/json"],
        "outputModes": ["application/json"],
    }],
}


class SettlementRequest(BaseModel):
    """What the settlement agent understood from the messages."""

    batch: str | None
    approval_ref: str | None
    incident: str | None


SETTLEMENT = ("You are the Settlement team's agent at Meridian Exchange. Read the request (all its text and data parts) and extract: "
              "the batch id (e.g. batch-10:12), the on-call approval reference (APR-...), and the incident id. "
              "Leave a field empty if it is not in the request. Never guess.")


@dataclass
class SettlementAgent:
    """The other team's A2A server. Your code only sees its Agent Card and its JSON-RPC answers."""

    model: Any
    world: World
    post: Any
    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_key: dict[str, str] = field(default_factory=dict)
    texts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    finish_at: dict[str, float] = field(default_factory=dict)
    unauthorized: int = 0

    async def handle(self, request: dict[str, Any], token: str | None) -> dict[str, Any]:
        rid, method, params = request.get("id"), request.get("method"), request.get("params", {})
        if token != TOKEN:
            self.unauthorized += 1
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32001, "message": "Unauthorized: this agent needs a bearer token (see securitySchemes in the Agent Card)."}}
        if method == "SendMessage":
            result = await self._send(params.get("message", {}))
            if "error" not in result:
                result = {"task": result}  # SendMessageResponse: a Task (or a Message)
        elif method == "GetTask":
            result = self._get(params.get("id", ""))
        else:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        if "error" in result:
            return {"jsonrpc": "2.0", "id": rid, "error": result["error"]}
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    async def _send(self, message: dict[str, Any]) -> dict[str, Any]:
        parts = message.get("parts", [])
        data = {k: v for p in parts if isinstance(p.get("data"), dict) for k, v in p["data"].items()}
        key = data.get("idempotency_key")
        task_id = message.get("taskId")
        if key and key in self.by_key and not task_id:  # a new request with a key already seen: the same task, nothing new
            return self._get(self.by_key[key])
        if task_id and task_id not in self.tasks:
            return {"error": {"code": -32001, "message": f"Task not found: {task_id}"}}
        if task_id and self.tasks[task_id]["status"]["state"] != INPUT_REQUIRED:
            return self._get(task_id)
        if not task_id:  # a new task: a new resend
            task_id = f"task-{uuid.uuid4().hex[:8]}"
            self.tasks[task_id] = {"id": task_id, "contextId": message.get("contextId") or f"ctx-{uuid.uuid4().hex[:6]}",
                                   "status": {"state": SUBMITTED}, "artifacts": [], "metadata": {}}
            self.texts[task_id] = []
            self.post("settlement", "board", f"New task {task_id}: a new resend request", "a2a")
        if key:
            self.by_key[key] = task_id
            self.tasks[task_id]["metadata"]["idempotency_key"] = key
        self.texts[task_id].append(message)
        task = self.tasks[task_id]
        if task["metadata"].get("approval_ref"):  # batch and approval known: this answer should confirm the count
            if data.get("confirm_count") == CONFIRMATIONS:
                task["status"] = _status(WORKING, f"Resending {BATCH}. This takes a few seconds: poll GetTask.")
                self.finish_at[task_id] = time.monotonic() + WORK_SECONDS
            else:
                task["status"] = _confirm_question(f"That does not confirm {CONFIRMATIONS}. ")
            return self._get(task_id)
        understood = (await Agent(self.model, output_type=SettlementRequest, instructions=SETTLEMENT, name="settlement",
                                  retries=3).run(json.dumps(self.texts[task_id]))).output
        if understood.batch != BATCH:
            task["status"] = _status(REJECTED, f"Unknown batch {understood.batch!r}. Delayed batch today: {BATCH}.")
        elif not understood.approval_ref:
            task["status"] = _status(INPUT_REQUIRED, "I need the on-call's approval reference (APR-...) before resending. "
                                                       "Reply in this task (same taskId).")
        else:
            task["metadata"].update(batch=understood.batch, approval_ref=understood.approval_ref)
            task["status"] = _confirm_question("")
        return self._get(task_id)

    def _get(self, task_id: str) -> dict[str, Any]:
        task = self.tasks.get(task_id)
        if task is None:
            return {"error": {"code": -32001, "message": f"Task not found: {task_id}"}}
        if task["status"]["state"] == WORKING and time.monotonic() >= self.finish_at[task_id]:
            meta = task["metadata"]
            result = self.world.resend_confirmations(meta["batch"], meta.get("idempotency_key") or task_id, meta["approval_ref"], "settlement-agent")
            if result["outcome"] in ("completed", "already_done"):
                task["status"] = _status(COMPLETED, f"{meta['batch']} resent to settlement.")
                task["artifacts"] = [{"artifactId": f"receipt-{task_id}", "name": "resend-receipt",
                                      "parts": [{"data": {"batch": meta["batch"], "sent_at": result.get("time"),
                                                                          "outcome": result["outcome"]}}]}]
            else:
                task["status"] = _status(FAILED, result["detail"])
            self.post("settlement", "systems", f"{task_id}: resend_confirmations {meta['batch']} → {result['outcome']} · {result['detail']}", "action")
        return json.loads(json.dumps(task))


def _status(state: str, text: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    parts: list[dict[str, Any]] = [{"text": text}] + ([{"data": data}] if data else [])
    return {"state": state, "message": {"role": "ROLE_AGENT", "messageId": uuid.uuid4().hex[:8], "parts": parts}}


def _confirm_question(prefix: str) -> dict[str, Any]:
    return _status(INPUT_REQUIRED, f"{prefix}{BATCH} holds {CONFIRMATIONS} confirmations for {MEMBERS} members, and each one is charged. "
                                   'To resend, reply in this task with a data part {"confirm_count": ' + str(CONFIRMATIONS) + "}.",
                   {"confirmations": CONFIRMATIONS, "members": MEMBERS, "reply_with": "confirm_count"})


# The client side: what your code uses -------------------------------------------------------------


@dataclass
class A2ARun:
    model: Any
    world: World = field(default_factory=World)
    cards: dict[str, dict[str, str]] = field(default_factory=dict)
    feed: list[dict[str, str]] = field(default_factory=list)
    final: dict[str, Any] | None = None
    error: str | None = None
    running: bool = False
    seconds: float = 0.0
    calls: int = 0

    def __post_init__(self) -> None:
        self.server: SettlementAgent | None = None
        self.token = TOKEN
        self.request: dict[str, Any] = {}

    def set_card(self, name: str, status: str, activity: str = "") -> None:
        self.cards[name] = {"status": status, "activity": activity}

    def post(self, sender: str, to: str, text: str, kind: str = "message") -> None:
        self.feed.append({"time": self.world.now(), "from": sender, "to": to, "text": text, "kind": kind})

    def note(self, text: str) -> None:
        self.post("client", "board", text, "note")
        self.set_card("client", "working", text)

    def card(self) -> dict[str, Any]:
        self.post("client", "settlement", "GET /.well-known/agent-card.json", "a2a")
        return json.loads(json.dumps(CARD))

    async def _call(self, method: str, params: dict[str, Any], token: str | None) -> dict[str, Any]:
        self.calls += 1
        request = {"jsonrpc": "2.0", "id": self.calls, "method": method, "params": params}
        headers = "A2A-Version: 1.0" + (" · Authorization: Bearer …" if token else "")
        self.post("client", "settlement", f"POST · {headers} · {json.dumps(request)}", "a2a")
        self.set_card("settlement", "working", method)
        answer = await self.server.handle(request, token)
        body = answer.get("result") or answer.get("error")
        body = body.get("task", body)
        shown = f"{body.get('id', '')} · {body['status']['state']}: {_text(body)}" if "status" in body else json.dumps(body)
        self.post("settlement", "client", shown, "a2a")
        self.set_card("settlement", "done", shown)
        if "error" in answer:
            return {"error": answer["error"]}
        return answer["result"].get("task", answer["result"])

    async def send_message(self, message: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        """JSON-RPC SendMessage. message: {"role": "ROLE_USER", "parts": [...], "taskId"?: ..., "contextId"?: ...}

        The JSON-RPC result is {"task": {...}}; this helper returns the Task inside it. It adds the messageId."""
        message = {"messageId": uuid.uuid4().hex[:8], **message}
        return await self._call("SendMessage", {"message": message, "configuration": {"returnImmediately": True}}, token)

    async def get_task(self, task_id: str, token: str | None = None) -> dict[str, Any]:
        """JSON-RPC GetTask."""
        return await self._call("GetTask", {"id": task_id}, token)

    async def wait(self, seconds: float) -> None:
        await asyncio.sleep(min(seconds, 5))

    # Running ---------------------------------------------------------------------------------------

    def start(self) -> threading.Thread:
        self.running = True
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        return thread

    def _run(self) -> None:
        began = time.monotonic()
        try:
            asyncio.run(asyncio.wait_for(self._main(), MAX_SECONDS))
        except NotImplementedError:
            self.error = "Not written yet: starter/a2a_client.py. Write it, save the file and click Run again."
        except TimeoutError:
            self.error = f"Stopped after {MAX_SECONDS} seconds."
        except Exception as error:  # noqa: BLE001 - keep the board when a run fails
            self.error = f"{type(error).__name__}: {error}"
        finally:
            self.seconds = round(time.monotonic() - began, 1)
            self.running = False

    async def _main(self) -> None:
        self.model = patient(self.model)
        self.server = SettlementAgent(self.model, self.world, self.post)
        ref = self.world.approve("resend_confirmations", BATCH, "Settlement received the 10:12 batch late.", "on-call")
        self.request = {"incident": "INC-2", "batch": BATCH, "approval_ref": ref}
        self.post("on-call", "client", f"Approved: resend {BATCH} ({ref}). Ask settlement to do it.", "approved")
        self.set_card("on-call", "done", f"Approved resend {BATCH} ({ref})")
        self.set_card("client", "working", "Running your client…")
        self.final = await load_starter("a2a_client").resend(self)
        self.set_card("client", "done", f"Returned: {self.final.get('status', {}).get('state', self.final) if isinstance(self.final, dict) else self.final}")
        # Settlement keeps working after your client returns: let every task it accepted finish
        await asyncio.sleep(WORK_SECONDS + 0.2)
        for task_id in list(self.server.tasks):
            self.server._get(task_id)

    def verdict(self) -> list[tuple[bool, str]]:
        sent = self.world.count("resend_confirmations")
        tasks = len(self.server.tasks) if self.server else 0
        state = self.final.get("status", {}).get("state") if isinstance(self.final, dict) else None
        unauthorized = self.server.unauthorized if self.server else 0
        return [
            (sent == 1, "Batch resent exactly once" if sent == 1 else ("Batch never resent" if sent == 0 else f"Batch resent {sent} times: members charged {sent} times")),
            (tasks == 1, "One task for one request" if tasks == 1 else f"{tasks} tasks created for one request"),
            (state == COMPLETED, "Your client returned the task completed" if state == COMPLETED else f"Your client returned the task {state or 'without a task'}"),
            (unauthorized == 0, "Every call had the token" if not unauthorized else f"{unauthorized} calls refused: no token"),
        ]


def _text(task: dict[str, Any]) -> str:
    parts = task.get("status", {}).get("message", {}).get("parts", [])
    return " ".join(p["text"] if "text" in p else json.dumps(p.get("data")) for p in parts)
