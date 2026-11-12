"""Run from the repository root: uv run --locked streamlit run sessions/course-02-agentic-ai/07-multi-agent/lab/app.py"""

from __future__ import annotations

import streamlit as st

from meridian.lab import board, ui
from team import Team, runbook, students_orchestrator, students_pipeline, use_solutions
from world import INCIDENTS

GUIDE = {
    "Exercise 1 · Pipeline (45 min)": """
**Goal:** write the on-call runbook in code, and see where a fixed order breaks.
You work in tab **1 · Pipeline** and in the file `starter/pipeline.py`.

**1 · Write the runbook** · 10 min
- Open `starter/pipeline.py` and read the text at the top: the runbook and how to talk to an agent.
- Write `run_pipeline`: the steps of the runbook, in its order. Each step sends a message to one agent.

**2 · Run the easy incident** · 5 min
- Tab **1 · Pipeline** → click **INC-1 · A network change** → click **Run**.
- Watch the cards light up. Read the messages under them, top to bottom.
- At the end, compare **The team reports** with **The gateway really is**.

**3 · Run the hard incident** · 5 min
- Click **INC-2 · Site A's network is failing** → click **Run**.
- Compare the two results again.
- In the messages: what did Remediation do? Which card says **Not used**?

**4 · Fix your pipeline** · 15 min
- Change `starter/pipeline.py` so the team gets INC-2 right.
- Save the file and click **Run** again. No need to restart the app.
- Did an agent stop (red card, "stopped after 12 steps")? Read its grey **TOOL** lines: what was it looking for? What could your message to it say?

**5 · Compare** · 10 min
- Run **INC-1** again with your new pipeline.
- Open the table **Every run** at the bottom of the page. Compare your two INC-1 runs: model calls, tokens, seconds.

**Questions to discuss**
1. On INC-2, every agent did its own job well. So who failed?
2. Who in the team knew that site B could not be used? Did that reach Remediation?
3. Your fix made INC-2 work. What did it cost on INC-1?
4. Tomorrow a new incident needs another specialist. What do you have to change?
""",
    "Exercise 2 · Orchestrator (55 min)": """
**Goal:** replace your fixed order with an agent that decides whom to ask, and when.
You work in tab **2 · Orchestrator** and in the file `starter/orchestrator.py`. You may use an AI assistant.

**1 · Read** · 5 min
- Open `starter/orchestrator.py` and read the text at the top: what `build_orchestrator` must return, and the example tool.

**2 · Give the orchestrator its team** · 10 min
- One tool per agent it may call.
- The docstring of each tool is what the orchestrator reads to decide when to use it. Write it with care.

**3 · Write its instructions** · 15 min
- In `INSTRUCTIONS`: its job, whom to ask, what Remediation must receive, when to stop.
- You must be able to explain every line, even if an AI wrote it.

**4 · Run the hard incident** · 10 min
- Tab **2 · Orchestrator** → click **INC-2 · Site A's network is failing** → click **Run**.
- Watch the cards: do **Network** and **Database** light up at the same time?
- Read the message from **Orchestrator** to **Remediation**: what does it contain?
- Did an agent stop (red card)? Read its grey **TOOL** lines: what was it looking for?
- Wrong result? Change the instructions or the tools, save, click **Run** again.

**5 · Run the easy incident and compare** · 15 min
- Click **INC-1 · A network change** → click **Run**.
- In **Every run**, compare the orchestrator with your pipeline on both incidents: result, model calls, tokens, seconds.

**Questions to discuss**
1. Did Network and Database work at the same time? How many seconds did that save?
2. Which line of your instructions made the right information reach Remediation?
3. On INC-1, which cost more: the pipeline or the orchestrator? Why?
4. When would you choose a pipeline, and when an orchestrator?
""",
}

NAMES = {"pipeline": "Pipeline", "orchestrator": "Orchestrator", "network": "Network", "database": "Database",
         "remediation": "Remediation", "reviewer": "Reviewer", "on-call": "On-call (you)", "team": "Team", "systems": "Systems"}
ROLES = {"pipeline": "your code · fixed order", "orchestrator": "an agent · decides whom to ask", "network": "investigates · changes nothing",
         "database": "investigates · changes nothing", "remediation": "acts · needs approval", "reviewer": "checks the real state",
         "on-call": "approves every action"}

TABS = {
    "pipeline": {"label": "1 · Pipeline", "pattern": students_pipeline, "agents": ["pipeline", "network", "database", "remediation"],
                 "intro": "The order is fixed in your code: `starter/pipeline.py`."},
    "orchestrator": {"label": "2 · Orchestrator", "pattern": students_orchestrator, "agents": ["orchestrator", "network", "database", "remediation"],
                  "intro": "An agent decides whom to ask and when: `starter/orchestrator.py`."},
    "demo": {"label": "Demo · Human in the loop", "pattern": runbook, "agents": ["pipeline", "network", "database", "remediation", "on-call", "reviewer"],
             "intro": "The runbook pipeline (network → remediation). Add a person and a reviewer to the loop."},
}

ui.page("Multi-Agent Lab · The incident room", GUIDE)
if use_solutions():
    st.caption("Running the solutions (LAB_SOLUTIONS=1), not starter/.")


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
    if key != "orchestrator":
        team.set_card("pipeline", "working", "Running the steps in order…")
    st.session_state[f"team_{key}"] = team
    st.session_state[f"logged_{key}"] = False
    team.start(TABS[key]["pattern"])


def record(key: str, team: Team) -> None:
    if key != "orchestrator":
        team.set_card("pipeline", "error" if team.error else "done", "Stopped." if team.error else "All steps done.")
    if team.error and key == "orchestrator":
        team.set_card("orchestrator", "error", "Stopped.")
    if team.error:  # a run that did not finish is not a result to compare
        return
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
    if finished and not team.error:
        state = team.world.gateway_now()
        recovered = team.world.recovered()
        left, right, _ = st.columns([1, 1, 2])
        left.metric("The team reports", team.reported)
        right.metric("The gateway really is", "recovered" if recovered else "NOT recovered")
        right.caption(f"Site {state['site']} · {state['latency_ms']} ms · {state['error_rate']:.0%} errors")
        if team.reported == "resolved" and not recovered:
            st.error("False 'resolved': the team says it is fixed, the system says it is not.")
    if finished and team.feed:
        board.copy_button(board.as_text(team.feed, NAMES))
    if team.feed or not team.error:
        board.feed(team.feed, NAMES)
    if finished and not st.session_state.get(f"logged_{key}"):
        record(key, team)
        st.session_state[f"logged_{key}"] = True
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
