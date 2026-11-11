"""Run from the repository root: uv run --locked streamlit run sessions/course-02-agentic-ai/07-multi-agent/lab/app.py"""

from __future__ import annotations

import streamlit as st

from meridian.lab import board, ui
from team import Team, runbook, students_commander, students_pipeline
from world import INCIDENTS

GUIDE = """
**The incident room.** Five agents, one incident. Watch who works, who talks to whom, and what they do.

**1 · Pipeline** — you fix the order in code (`starter/pipeline.py`).
- Write the runbook: network finds the cause, remediation fixes it.
- Run INC-1, then INC-2. On INC-2, what did remediation do? Who knew it was a bad idea?
- Add the database specialist. Run both again and compare in **Every run**.

**2 · Commander** — an agent decides whom to ask (`starter/commander.py`).
- Build the commander: its tools are the other agents.
- Run both incidents. Do network and database work at the same time?
- Compare with your pipeline: result, calls, tokens, seconds.

**Demo** — the trainer runs it: a person and a reviewer in the loop.
"""

NAMES = {"pipeline": "Pipeline", "commander": "Commander", "network": "Network", "database": "Database",
         "remediation": "Remediation", "reviewer": "Reviewer", "on-call": "On-call (you)", "team": "Team", "world": "Systems"}
ROLES = {"pipeline": "your code · fixed order", "commander": "an agent · decides whom to ask", "network": "investigates · changes nothing",
         "database": "investigates · changes nothing", "remediation": "acts · needs approval", "reviewer": "checks the real state",
         "on-call": "approves every action"}

TABS = {
    "pipeline": {"label": "1 · Pipeline", "pattern": students_pipeline, "agents": ["pipeline", "network", "database", "remediation"],
                 "intro": "The order is fixed in your code: `starter/pipeline.py`."},
    "commander": {"label": "2 · Commander", "pattern": students_commander, "agents": ["commander", "network", "database", "remediation"],
                  "intro": "An agent decides whom to ask and when: `starter/commander.py`."},
    "demo": {"label": "Demo · Human in the loop", "pattern": runbook, "agents": ["pipeline", "network", "database", "remediation", "on-call", "reviewer"],
             "intro": "The runbook pipeline (network → remediation). Add a person and a reviewer to the loop."},
}

ui.page("Multi-Agent Lab · The incident room", GUIDE)


def start(key: str) -> None:
    try:
        model = ui.get_model()
    except ValueError as error:
        st.error(str(error))
        return
    demo = key == "demo"
    team = Team(model, st.session_state[f"incident_{key}"],
                approvals="human" if demo and st.session_state.get("human") else "auto",
                reviewer=demo and bool(st.session_state.get("reviewer")))
    if key != "commander":
        team.set_card("pipeline", "working", "Running the steps in order…")
    st.session_state[f"team_{key}"] = team
    st.session_state[f"logged_{key}"] = False
    team.start(TABS[key]["pattern"])


def record(key: str, team: Team) -> None:
    if key != "commander" and not team.error:
        team.set_card("pipeline", "done", "All steps done.")
    st.session_state.setdefault("runs", []).append({
        "Tab": TABS[key]["label"], "Incident": team.incident.split(" · ")[0],
        "Setup": ("person approves" if team.approvals == "human" else "auto-approve") + (" + reviewer" if team.reviewer else ""),
        "Team reports": team.reported, "Really": "recovered" if team.world.recovered() else "NOT recovered",
        "Model calls": team.requests, "Tokens": team.tokens, "Seconds": team.seconds,
    })
    st.session_state[f"logged_{key}"] = True


def approval(team: Team) -> None:
    pending = team.pending
    with st.container(border=True):
        st.markdown(f"**{NAMES.get(pending['agent'], pending['agent'])} asks you to approve:** `{pending['action']} {pending['target']}`")
        st.caption(pending["reason"])
        comment = st.text_input("Comment (optional, the agent reads it)", key=f"comment_{id(pending)}")
        yes, no, _ = st.columns([1, 1, 4])
        if yes.button("Approve", type="primary", key=f"yes_{id(pending)}", width="stretch"):
            team.answer(True, comment)
        if no.button("Reject", key=f"no_{id(pending)}", width="stretch"):
            team.answer(False, comment)


def room(key: str) -> None:
    team: Team | None = st.session_state.get(f"team_{key}")
    agents = TABS[key]["agents"]
    finished = team is not None and not team.running
    items = []
    for agent in agents:
        card = team.cards.get(agent) if team else None
        status = card["status"] if card else ("unused" if finished else "idle")
        items.append({"name": NAMES[agent], "role": ROLES[agent], "status": status, "activity": card["activity"] if card else ""})
    board.cards(items)
    if team is None:
        st.caption("Pick an incident and run the team.")
        return
    if team.pending:
        approval(team)
    if team.error:
        (st.info if team.error.startswith("Not written") else st.error)(team.error)
    if finished:
        state = team.world.gateway_now()
        recovered = team.world.recovered()
        left, right, _ = st.columns([1, 1, 2])
        left.metric("The team reports", team.reported)
        right.metric("The gateway really is", "recovered" if recovered else "NOT recovered")
        right.caption(f"Site {state['site']} · {state['latency_ms']} ms · {state['error_rate']:.0%} errors")
        if team.reported == "resolved" and not recovered:
            st.error("False 'resolved': the team says it is fixed, the system says it is not.")
    board.feed(team.feed, NAMES)
    if finished and not st.session_state.get(f"logged_{key}"):
        record(key, team)
        st.rerun()


tabs = st.tabs([tab["label"] for tab in TABS.values()])
for tab, key in zip(tabs, TABS):
    with tab:
        st.caption(TABS[key]["intro"])
        pick, *switches, go = st.columns([3, 1, 1, 1] if key == "demo" else [5, 1], vertical_alignment="bottom")
        pick.segmented_control("Incident", list(INCIDENTS), key=f"incident_{key}", default=list(INCIDENTS)[1 if key == "demo" else 0])
        if key == "demo":
            switches[0].toggle("A person approves", key="human")
            switches[1].toggle("Reviewer", key="reviewer")
        running = any(st.session_state.get(f"team_{k}") and st.session_state[f"team_{k}"].running for k in TABS)
        if go.button("Run", type="primary", key=f"run_{key}", width="stretch", disabled=running or not st.session_state.get(f"incident_{key}")):
            start(key)
        live = st.session_state.get(f"team_{key}")
        st.fragment(run_every=0.8 if live and live.running else None)(room)(key)

if st.session_state.get("runs"):
    st.markdown("**Every run**")
    st.dataframe(st.session_state["runs"], hide_index=True, width="stretch")
