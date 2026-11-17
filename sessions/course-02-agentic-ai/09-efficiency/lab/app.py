"""Run from the repository root: uv run --locked streamlit run sessions/course-02-agentic-ai/09-efficiency/lab/app.py"""

from __future__ import annotations

import streamlit as st
from codemode import SAFE, TASK, Duel, blocked_example
from common import LARGE, SMALL, models, use_solutions
from gateway import REQUESTS, Replay
from storm import BUDGET, INCIDENT_COST, RATE_LIMIT, Storm, alerts

from meridian.lab import ui

GUIDE = {
    "Exercise 1 · Alert storm (45 min)": """
**Goal:** find the incident that matters in 500 alerts, with 30 model calls.
You work in tab **1 · Alert storm** and in the file `starter/storm.py`.

**1 · See the problem** · 5 min
- Tab **1 · Alert storm** → click **Run**.
- Watch the budget and the table: what does the triage agent look at? Is the incident that matters ever found?

**2 · Look at the alerts** · 10 min
- Open **The 500 alerts** under the button. Sort and read the columns.
- Which components and rules repeat hundreds of times? Where is the incident that matters?

**3 · Write the policy** · 25 min
- In `starter/storm.py`, change `group`, `order` and `TRIAGE_INSTRUCTIONS`.
- Save and click **Run** again. Goal: the incident that matters is opened, no incident is opened for noise, budget left.

**4 · Compare** · 5 min
- In **Every run**, compare your runs: result, calls used, seconds.

**Questions to discuss**
1. Which decisions did you take without the model? Which needed the model?
2. "critical" alerts from staging: why did they not deserve the first calls?
3. Your budget ends in the middle of the storm. What do you sacrifice, and how would you know?
4. The provider allows 8 calls a minute. What happens if 3 storms arrive at the same time?
""",
    "Exercise 2 · AI gateway (50 min)": """
**Goal:** answer a morning of requests for less money, without one wrong answer and without leaking anything.
You work in tab **2 · AI gateway** and in the file `starter/gateway.py`.

**1 · See the problem** · 10 min
- Tab **2 · AI gateway** → click **Run**. The 12 requests are replayed through your gateway, in order.
- Read the table row by row: who served each request (cache, small, large)? Which answers are wrong, and why?
- Open **The 12 requests** to read what each one asks and who asks it.

**2 · Route** · 10 min
- In `starter/gateway.py`, write `route()`: which requests need the large model, which the small one, which no model at all?
- Save and click **Run** again. Watch the cost and the right answers.

**3 · A cache that is safe** · 15 min
- Write `reuse()`. Find the rows where the cache served an answer that was wrong for that request, or for that person.
- What must match, besides similar words?

**4 · Plan B** · 10 min
- Request R10 meets an outage of the large model. Write `on_error()`.

**5 · Compare** · 5 min
- In **Every run**: right answers, leaks, failures, cost. Did you keep 12 of 12?

**Questions to discuss**
1. Which request did the small model get wrong? What would that cost in a real incident?
2. Two questions read the same and needed different answers. What else did you compare?
3. During the outage, is a weaker answer better than no answer? For which kinds of request?
4. Where would you put this gateway: in each agent, or as one service for every agent of the company?
""",
}

ui.page("Efficiency Lab · Budgets, routing and cache", GUIDE)
if use_solutions():
    st.caption("Running the solutions (LAB_SOLUTIONS=1), not starter/.")


def busy() -> bool:
    return any(getattr(st.session_state.get(key), "running", False) for key in ("storm", "replay", "duel"))


def checklist(checks: list[tuple[bool, str]]) -> None:
    st.markdown("  \n".join(f":green[✓ {text}]" if ok else f":red[**✗ {text}**]" for ok, text in checks))


def errors(run) -> None:
    if run.error:
        (st.info if run.error.startswith("Not written") else st.error)(run.error)


def start(key: str, run) -> None:
    st.session_state[key] = run
    st.session_state[f"logged_{key}"] = False
    run.start()


def live(key: str, view) -> None:
    run = st.session_state.get(key)
    st.fragment(run_every=0.8 if run is not None and run.running else None)(view)()


def finish(key: str, tab: str, row: dict) -> None:
    run = st.session_state[key]
    if not run.running and not st.session_state.get(f"logged_{key}"):
        st.session_state[f"logged_{key}"] = True
        if not run.error:
            checks = run.verdict()
            st.session_state.setdefault("runs", []).append({"Tab": tab, **row, "Seconds": run.seconds,
                "Result": "all green" if all(ok for ok, _ in checks) else "; ".join(t for ok, t in checks if not ok)})
        st.rerun()


# 1 · Storm ------------------------------------------------------------------------------------------------


def storm_view() -> None:
    storm: Storm | None = st.session_state.get("storm")
    if storm is None:
        st.caption("Run the storm.")
        return
    a, b, c, d = st.columns(4)
    a.metric("Budget used", f"{storm.used} / {BUDGET}")
    b.metric("Minutes", storm.minute)
    c.metric("Groups", storm.groups)
    d.metric("Alerts never looked at", storm.unseen if storm.rows else "–")
    st.progress(min(storm.used / BUDGET, 1.0))
    errors(storm)
    if not storm.running and not storm.error:
        checklist(storm.verdict())
    if storm.rows:
        st.dataframe([{k: v for k, v in row.items() if k not in ("alerts", "matters")} for row in storm.rows], hide_index=True, width="stretch")
    if not storm.running:
        finish("storm", "1 · Storm", {"Model calls": storm.used})


# 2 · Gateway ----------------------------------------------------------------------------------------------


def replay_view() -> None:
    replay: Replay | None = st.session_state.get("replay")
    if replay is None:
        st.caption("Run the morning through your gateway.")
        return
    totals = replay.totals()
    a, b, c, d = st.columns(4)
    a.metric("Right answers", f"{totals['right']} / {len(REQUESTS)}" if replay.rows else "–")
    b.metric("Cost", f"${totals['cost']:.4f}")
    c.metric("Served from cache", totals["cache"])
    d.metric("Leaks", totals["leaks"])
    errors(replay)
    if not replay.running and not replay.error:
        checklist(replay.verdict())
    if replay.rows:
        rows = [{k: v for k, v in row.items() if k != "ok"} for row in replay.rows]
        st.dataframe(rows, hide_index=True, width="stretch",
                     column_config={"Result": st.column_config.TextColumn(width="large")})
    if not replay.running:
        finish("replay", "2 · Gateway", {"Cost $": totals["cost"]})


# Demo · Code mode ----------------------------------------------------------------------------------------


def duel_view() -> None:
    duel: Duel | None = st.session_state.get("duel")
    if duel is None:
        return
    errors(duel)
    columns = st.columns(2)
    for column, name in zip(columns, ("Tools, one by one", "Code mode"), strict=True):
        with column, st.container(border=True):
            st.markdown(f"**{name}**")
            result = duel.results.get(name)
            if result is None:
                st.caption("Working…" if duel.running else "")
                continue
            m1, m2, m3 = st.columns(3)
            m1.metric("Model calls", result["Model calls"])
            m2.metric("Tokens", f"{result['Tokens']:,}")
            m3.metric("Seconds", result["Seconds"])
            st.caption(result["answer"][:600])
    for script in duel.scripts:
        st.code(script, language="python")


storm_tab, gateway_tab, demo_tab = st.tabs(["1 · Alert storm", "2 · AI gateway", "Demo · Code mode"])
running = busy()

with storm_tab:
    st.caption(f"500 alerts in 5 minutes. Budget: {BUDGET} model calls; {RATE_LIMIT} per minute; an incident costs {INCIDENT_COST}. "
               "Your policy: `starter/storm.py`.")
    _, go = st.columns([5, 1], vertical_alignment="bottom")
    if go.button("Run", type="primary", key="run_storm", width="stretch", disabled=running):
        try:
            start("storm", Storm(models(ui.get_model())["small"]))
        except ValueError as error:
            st.error(str(error))
    with st.expander("The 500 alerts"):
        st.dataframe(alerts(), hide_index=True, width="stretch",
                     column_order=["id", "time", "source", "component", "rule", "severity", "env", "message"])
    live("storm", storm_view)

with gateway_tab:
    st.caption(f"A morning of the incident team: 12 requests. Small model: {SMALL}. Large model: {LARGE}. Your gateway: `starter/gateway.py`.")
    _, go = st.columns([5, 1], vertical_alignment="bottom")
    if go.button("Run", type="primary", key="run_replay", width="stretch", disabled=running):
        try:
            start("replay", Replay(ui.get_model()))
        except ValueError as error:
            st.error(str(error))
    with st.expander("The 12 requests"):
        st.dataframe([{k: r[k] for k in ("id", "kind", "role", "incident", "question", "context")} for r in REQUESTS],
                     hide_index=True, width="stretch")
    live("replay", replay_view)

with demo_tab:
    st.caption("The same check, two ways: calling tools one by one, or writing one script that runs in a sandbox.")
    st.markdown(f"> {TASK}")
    left, right = st.columns([5, 1], vertical_alignment="bottom")
    left.caption(f"Sandbox: no imports; builtins: {', '.join(SAFE)}; 5 seconds; 4 000 characters of output.")
    if right.button("Run both", type="primary", key="run_duel", width="stretch", disabled=running):
        try:
            start("duel", Duel(models(ui.get_model())["large"]))
        except ValueError as error:
            st.error(str(error))
    with st.expander("What the sandbox does with `import os`"):
        st.code("import os\nprint(os.listdir('/'))", language="python")
        st.code(blocked_example(), language="text")
    live("duel", duel_view)

if st.session_state.get("runs"):
    st.markdown("**Every run**")
    st.dataframe(st.session_state["runs"], hide_index=True, width="stretch")
