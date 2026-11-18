"""Run from the repository root: uv run --locked streamlit run sessions/course-02-agentic-ai/09-llm-gateway/lab/app.py"""

from __future__ import annotations

import streamlit as st
from common import LARGE, SMALL, use_solutions
from gateway import MAX_DEFERS, OUTAGE, RATE_LIMIT, REQUESTS, Replay

from meridian.lab import ui

GUIDE = """
**Goal:** answer Black Friday's 15 requests right, for less money, without showing one customer's data to another,
and without dropping a request when the provider struggles. You work in this page and in the file `starter/gateway.py`.

**1 · See the problem** · 10 min
- Click **Run**. The 15 requests go through your gateway, in order.
- Read the table row by row: who served each request (cache, none, small, large, backup)? Which rows are red, and why?
- Open **The 15 requests** under the button: what does each customer ask, and with which facts?

**2 · Route** · 10 min
- Write `route()`: which requests need the large model, which the small one, which no model at all?
- Save, click **Run** again. Watch the cost and the right answers.

**3 · A cache that is safe** · 15 min
- Write `reuse()`. Find the rows where the cache served an answer that belonged to another customer, or that was out of date.
- What must match, besides similar words?

**4 · The rush** · 10 min
- At 10:30 six requests arrive in the same minute. Provider A allows 3 model calls a minute; the next one gets a 429.
- Write `admit()`: which requests can wait a minute (`"defer"`), and which cannot?

**5 · Plan B** · 10 min
- At 11:40 provider A's large model is down. Write `on_error()`.

**6 · Compare** · 5 min
- In **Every run**: right answers, leaks, cost. Did you keep 15 of 15 with fewer calls to the large model?

**Questions to discuss**
1. Which request did the small model get wrong? What would that cost the shop?
2. Two customers asked "Where is my order?". What did the cache need to know before reusing an answer?
3. The discount changed at noon. How does a real cache know an answer is out of date?
4. In the rush, who waited, and who never should? Who decides that: the gateway or each agent?
5. During the outage, why another provider and not the small model? When would the small model be fine?
"""

ui.page("LLM Gateway Lab · Ribeira Home", GUIDE)
if use_solutions():
    st.caption("Running the solutions (LAB_SOLUTIONS=1), not starter/.")


def checklist(checks: list[tuple[bool, str]]) -> None:
    st.markdown("  \n".join(f":green[✓ {text}]" if ok else f":red[**✗ {text}**]" for ok, text in checks))


def replay_view() -> None:
    replay: Replay | None = st.session_state.get("replay")
    if replay is None:
        st.caption("Run Black Friday through your gateway.")
        return
    totals = replay.totals()
    a, b, c, d = st.columns(4)
    a.metric("Right answers", f"{totals['right']} / {len(REQUESTS)}" if replay.rows else "–")
    b.metric("Cost", f"${totals['cost']:.4f}")
    c.metric("Served from cache", totals["cache"])
    d.metric("Leaks", totals["leaks"])
    if replay.error:
        (st.info if replay.error.startswith("Not written") else st.error)(replay.error)
    if not replay.running and not replay.error:
        checklist(replay.verdict())
    if replay.rows:
        rows = [{k: v for k, v in row.items() if k != "ok"} for row in replay.rows]
        st.dataframe(rows, hide_index=True, width="stretch", column_config={"Result": st.column_config.TextColumn(width="large")})
    if not replay.running and not st.session_state.get("logged_replay"):
        st.session_state["logged_replay"] = True
        if not replay.error:
            checks = replay.verdict()
            st.session_state.setdefault("runs", []).append({
                "Right": totals["right"], "Leaks": totals["leaks"], "Large first": totals["large"], "From cache": totals["cache"],
                "Cost $": totals["cost"], "Seconds": replay.seconds,
                "Result": "all green" if all(ok for ok, _ in checks) else "; ".join(t for ok, t in checks if not ok)})
        st.rerun()


st.caption(f"Ribeira Home's support assistant on Black Friday: 15 requests. Provider A: small {SMALL}, large {LARGE}, "
           f"{RATE_LIMIT} calls a minute; its large model is down {OUTAGE[0]}–{OUTAGE[1]}. Provider B: backup, a strong model. "
           f"A request deferred more than {MAX_DEFERS} times gets a 'we are busy' reply. Your gateway: `starter/gateway.py`.")
_, go = st.columns([5, 1], vertical_alignment="bottom")
replay = st.session_state.get("replay")
if go.button("Run", type="primary", key="run_replay", width="stretch", disabled=bool(replay and replay.running)):
    try:
        st.session_state["replay"] = Replay(ui.get_model())
        st.session_state["logged_replay"] = False
        st.session_state["replay"].start()
    except ValueError as error:
        st.error(str(error))
with st.expander("The 15 requests"):
    st.dataframe([{k: r[k] for k in ("id", "time", "kind", "customer", "question", "context")} for r in REQUESTS],
                 hide_index=True, width="stretch")
replay = st.session_state.get("replay")
st.fragment(run_every=0.8 if replay is not None and replay.running else None)(replay_view)()

if st.session_state.get("runs"):
    st.markdown("**Every run**")
    st.dataframe(st.session_state["runs"], hide_index=True, width="stretch")
