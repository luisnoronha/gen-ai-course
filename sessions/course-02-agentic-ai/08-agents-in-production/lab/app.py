"""Run from the repository root: uv run --locked streamlit run sessions/course-02-agentic-ai/08-agents-in-production/lab/app.py"""

from __future__ import annotations

import streamlit as st
from a2a import CARD, A2ARun
from room import SCENARIOS, Room, use_solutions
from traces import Review, record_live, recorded, waterfall_rows
from workers import Fleet

from meridian.lab import board, ui

GUIDE = {
    "Exercise 1 · A2A (35 min)": """
**Goal:** get another team's agent to do something for you, once, through the A2A protocol.
You work in tab **1 · Ask another team's agent** and in the file `starter/a2a_client.py`.

**1 · See the problem** · 5 min
- Tab **1 · Ask another team's agent** → click **Run**.
- Watch the messages: every **A2A** line is a JSON-RPC call (`SendMessage`, `GetTask`) or its answer. How many tasks were created? How many resends?
- Settlement asked the client a question. Which one? Where did the client answer it?

**2 · Read the Agent Card** · 5 min
- Open **The Settlement Agent's card** under the button. Read the skill's description to the end.
- What does the skill need? How does it authenticate? What does it say about sending a request twice?

**3 · Write the client** · 20 min
- In `starter/a2a_client.py`, change `resend()`.
- Save and click **Run** again. The goal: every line green.
- The blue **YOUR CODE** lines show what your client decided.

**4 · Compare** · 5 min
- In **Every run**, compare your runs.

**Questions to discuss**
1. The task said TASK_STATE_WORKING. Why is sending the request again different from asking for its state?
2. The agent asked you a question. Why answer inside the same task, and not in a new message?
3. Your client cannot see settlement's systems. How do you know the resend happened, and only once?
4. When is A2A better than giving your agent a tool that calls settlement's API directly?
""",
    "Exercise 2 · Traces (45 min)": """
**Goal:** find what went wrong in an agent team only from its traces, and write the monitors that would have warned you.
You work in tab **2 · Find the cause in the traces** and in the file `starter/monitors.py`.

**1 · Read the traces** · 15 min
- Tab **2 · Find the cause in the traces** → pick **Trace 1**, then 2, 3 and 4.
- Read each waterfall top to bottom (blue = agent, purple = model call, grey = tool call). Hover a row to see the tool's result.
- Open **One span, as OpenTelemetry records it** and pick a few spans: trace_id, span_id, parent, and the `gen_ai.*` attributes.
- For each trace: was it fixed? If not, which agent went wrong first? Write your answer down.

**2 · See the naive watch** · 5 min
- Click **Run monitors and analyst**.
- Which traces did the monitors catch? What did the analyst say? Compare with your answers.

**3 · Write the monitors and the analyst** · 20 min
- In `starter/monitors.py`: write monitors (code), `describe(trace)` (what the analyst sees) and `ANALYST_INSTRUCTIONS`.
- Save and click **Run monitors and analyst** again.
- Goal: problems caught and no false alarm on the healthy trace (the green and red lines check this); and the analyst names the real cause (you check this one, against **What really happened**).
- Open **What really happened** under each answer only after you have your own.

**4 · A live run** (optional) · 5 min
- Click **Record a live run**: the team of session 7 runs on INC-2 with the real model (about 30 s). Your monitors run on it too.

**Questions to discuss**
1. Only one of the three problems raised an error. What does "it went wrong" look like in the other two?
2. Which of your monitors would you page someone for at 3 a.m.? Which only go on a dashboard?
3. What did your analyst need to see that the naive describe() did not show?
4. Session 6 evaluated before launch. What can only be seen in production?
""",
    "Exercise 3 · Resume after a crash (45 min)": """
**Goal:** continue an incident after a crash without repeating what was already done, and without using what is no longer valid.
You work in tab **3 · Resume after a crash** and in the file `starter/resume.py`.

**1 · See the problem** · 10 min
- Tab **3 · Resume after a crash** → click **A · Crash after the resend** → click **Run**.
- Watch the board: findings, plan, approvals, the failover, the resend… then the red **CRASH**.
- After the crash, your `resume.py` runs. Which line of the result is red?
- Open **Checkpoint (what was saved)**: what does it say about step 2? Is it true?

**2 · Make the resume safe** · 20 min
- Read the text at the top of `starter/resume.py`, then change `resume()`.
- Save and click **Run** again until scenario A ends all green.

**3 · A long pause** · 15 min
- Click **B · Crash, then a long pause** → **Run**. What changed while nobody was working?
- Change `resume()` so both A and B end green.

**Questions to discuss**
1. After the crash, where is the truth: in the checkpoint, in the systems, or in the agent's memory?
2. The checkpoint said step 2 was "started". Done or not done? How do you know?
3. What can a resume reuse from before the crash, and what must it check again?
4. In exercise 1, what should go into the checkpoint so that a crash in the middle of the A2A task is safe?
""",
}

NAMES = {"team": "Team", "resume": "Your resume", "client": "Your client", "settlement": "Settlement Agent (A2A)",
         "network": "Network", "database": "Database", "remediation": "Remediation", "reviewer": "Reviewer", "on-call": "On-call",
         "checkpoint": "Checkpoint", "systems": "Systems", "board": "Board", "worker-1": "Worker 1", "worker-2": "Worker 2",
         "store": "Shared store"}
ROLES = {"network": "investigates", "database": "investigates", "remediation": "acts · needs approval", "on-call": "approves",
         "checkpoint": "saved after each step", "resume": "your code, after the crash", "reviewer": "checks the real state",
         "client": "your code, your team", "settlement": "another team's agent",
         "worker-1": "takes incidents from the queue", "worker-2": "takes incidents from the queue", "store": "who has which incident"}

ui.page("Agents in Production Lab", GUIDE)
if use_solutions():
    st.caption("Running the solutions (LAB_SOLUTIONS=1), not starter/.")


def busy() -> bool:
    return any(getattr(st.session_state.get(key), "running", False) for key in ("a2a", "review", "room", "fleet"))


def checklist(checks: list[tuple[bool, str]]) -> None:
    st.markdown("  \n".join(f":green[✓ {text}]" if ok else f":red[**✗ {text}**]" for ok, text in checks))


def cards(run, agents: list[str]) -> None:
    finished = not run.running
    board.cards([{"name": NAMES[a], "role": ROLES[a], "status": run.cards.get(a, {}).get("status", "unused" if finished else "idle"),
                  "activity": run.cards.get(a, {}).get("activity", "")} for a in agents])


def errors(run) -> None:
    if run.error:
        (st.info if run.error.startswith("Not written") else st.error)(run.error)


def finish(key: str, tab: str, setup: str, calls) -> None:
    run = st.session_state[key]
    if not run.running and not st.session_state.get(f"logged_{key}"):
        st.session_state[f"logged_{key}"] = True
        if not run.error:
            checks = run.verdict()
            st.session_state.setdefault("runs", []).append({
                "Tab": tab, "Setup": setup, "Model calls": calls(run), "Seconds": run.seconds,
                "Result": "all green" if all(ok for ok, _ in checks) else "; ".join(t for ok, t in checks if not ok)})
        st.rerun()


def start(key: str, run) -> None:
    st.session_state[key] = run
    st.session_state[f"logged_{key}"] = False
    run.start()


def live(key: str, view) -> None:
    run = st.session_state.get(key)
    st.fragment(run_every=0.8 if run is not None and run.running else None)(view)()


def feed(run) -> None:
    if not run.running and run.feed:
        board.copy_button(board.as_text(run.feed, NAMES))
    board.feed(run.feed, NAMES)


# 1 · A2A ------------------------------------------------------------------------------------------------


def a2a_view() -> None:
    run: A2ARun | None = st.session_state.get("a2a")
    if run is None:
        st.caption("Run your client.")
        return
    cards(run, ["client", "settlement", "on-call"])
    errors(run)
    if not run.running and not run.error:
        checklist(run.verdict())
    feed(run)
    finish("a2a", "1 · A2A", "your client", lambda r: r.calls)


# 2 · Traces ---------------------------------------------------------------------------------------------


def review_view() -> None:
    review: Review | None = st.session_state.get("review")
    if review is None:
        return
    if review.running:
        st.caption("Your monitors and your analyst are reading every trace…")
        return
    errors(review)
    if review.error:
        return
    checklist(review.verdict())
    for row in review.rows:
        with st.container(border=True):
            st.markdown(f"**{row['trace']}**")
            st.markdown("Monitors: " + (", ".join(f"`{a}`" for a in row["alerts"]) if row["alerts"] else "_silent_"))
            st.markdown(f"Analyst: {row['analyst']}")
            with st.expander("What really happened"):
                st.write(row["what_happened"])
    finish("review", "2 · Traces", "your monitors", lambda r: r.calls)


# 3 · Resume -----------------------------------------------------------------------------------------------


def room_view() -> None:
    room: Room | None = st.session_state.get("room")
    if room is None:
        st.caption("Pick a scenario and run.")
        return
    cards(room, ["network", "database", "remediation", "on-call", "checkpoint", "resume", "reviewer"])
    errors(room)
    if not room.running and not room.error:
        checklist(room.verdict())
    if room.path.exists() and room.crashed:
        with st.expander("Checkpoint (what was saved)"):
            st.code(room.path.read_text(encoding="utf-8"), language="json")
    feed(room)
    finish("room", "3 · Resume", room.scenario_label, lambda r: r.requests)


# Demo -------------------------------------------------------------------------------------------------------


def fleet_view() -> None:
    fleet: Fleet | None = st.session_state.get("fleet")
    if fleet is None:
        st.caption("Choose where the state lives, and run.")
        return
    cards(fleet, ["worker-1", "worker-2", "store"])
    errors(fleet)
    if not fleet.running and not fleet.error:
        checklist(fleet.verdict())
    board.feed(fleet.feed, NAMES)
    if not fleet.running and not st.session_state.get("logged_fleet"):
        st.session_state["logged_fleet"] = True
        st.rerun()


a2a_tab, traces_tab, resume_tab, demo_tab = st.tabs(
    ["1 · Ask another team's agent", "2 · Find the cause in the traces", "3 · Resume after a crash", "Demo · Two workers"])
running = busy()

with a2a_tab:
    st.caption("Settlement's systems belong to another team. Their agent speaks A2A. Your client: `starter/a2a_client.py`.")
    _, go = st.columns([5, 1], vertical_alignment="bottom")
    if go.button("Run", type="primary", key="run_a2a", width="stretch", disabled=running):
        try:
            start("a2a", A2ARun(ui.get_model()))
        except ValueError as error:
            st.error(str(error))
    with st.expander("The Settlement Agent's card"):
        st.json(CARD)
    live("a2a", a2a_view)

with traces_tab:
    st.caption("Recorded runs of the session 7 team, as OpenTelemetry spans. Your monitors and analyst: `starter/monitors.py`.")
    all_traces = recorded()
    titles = [trace.title for trace, _ in all_traces]
    pick, rec = st.columns([5, 1], vertical_alignment="bottom")
    pick.segmented_control("Trace", titles, key="trace", default=titles[0])
    if rec.button("Record a live run", key="record", width="stretch", disabled=running):
        try:
            ui.get_model()
            with st.spinner("The session 7 team is working on INC-2 with the real model…"):
                record_live()
            st.rerun()
        except ValueError as error:
            st.error(str(error))
        except Exception as error:  # noqa: BLE001 - show it, keep the page
            st.error(f"The live run failed: {error}")
    chosen = next((t for t, _ in all_traces if t.title == st.session_state.get("trace")), None)
    if chosen is not None:
        st.caption(f"{chosen.source}. Cost ${chosen.cost_usd():.4f}.")
        rows = waterfall_rows(chosen)
        board.waterfall(rows)
        with st.expander("One span, as OpenTelemetry records it"):
            labels = [f"{i + 1:02d} · {'· ' * row['depth']}{row['label']}" for i, row in enumerate(rows)]
            picked = st.selectbox("Span", labels, key=f"span_{chosen.name}", label_visibility="collapsed")
            st.json(rows[labels.index(picked)]["span"])
        st.dataframe([{"Agent": agent, **row} for agent, row in chosen.agents().items()], hide_index=True, width="stretch")
    if st.button("Run monitors and analyst", type="primary", key="run_review", disabled=running):
        try:
            start("review", Review(ui.get_model()))
        except ValueError as error:
            st.error(str(error))
    live("review", review_view)

with resume_tab:
    st.caption("The lab runs the first half of the incident and crashes. Your `starter/resume.py` continues.")
    pick, go = st.columns([5, 1], vertical_alignment="bottom")
    pick.segmented_control("Scenario", list(SCENARIOS), key="scenario", default=next(iter(SCENARIOS)))
    if go.button("Run", type="primary", key="run_room", width="stretch", disabled=running or not st.session_state.get("scenario")):
        try:
            room = Room(ui.get_model(), SCENARIOS[st.session_state["scenario"]])
            room.scenario_label = st.session_state["scenario"].split(" · ")[0]
            start("room", room)
        except ValueError as error:
            st.error(str(error))
    live("room", room_view)

with demo_tab:
    st.caption("Two workers take incidents from one queue. No model: the question is where the state lives.")
    pick, crash, go = st.columns([4, 1, 1], vertical_alignment="bottom")
    pick.segmented_control("State", ["In each worker's memory", "Shared, with a lease"], key="state", default="In each worker's memory")
    crash.toggle("Worker 1 crashes", key="crash")
    if go.button("Run", type="primary", key="run_fleet", width="stretch", disabled=running or not st.session_state.get("state")):
        start("fleet", Fleet("memory" if st.session_state["state"].startswith("In each") else "shared", crash=st.session_state.get("crash", False)))
    live("fleet", fleet_view)

if st.session_state.get("runs"):
    st.markdown("**Every run**")
    st.dataframe(st.session_state["runs"], hide_index=True, width="stretch")
