"""Run from the repository root: uv run --locked streamlit run sessions/course-02-agentic-ai/06-evaluation/lab/app.py"""

from __future__ import annotations

from dataclasses import replace

import streamlit as st

import agents
import loop
import suite
from meridian.lab import ui

GUIDE = """
Two steps, one per tab. The second uses the first.

**1 · Compare A and B**
- Run A and B with **1 repetition**. Which looks better? Then go to 3 repetitions. Does it hold?
- Write `starter/decision.py`: its decision shows under the table.
- Build your own agent in `starter/my_agent.py` (AI help allowed). Reload: **C** joins the comparison.
- Write `starter/trajectory.py`: its checks show in **Every run**.

**2 · Let the agents improve the agent**
- Start from B, or from your C. Run 3 iterations. Read each change, and why it was kept or not.
- Build the critic, the proposer and the memory in `starter/improver.py` (AI help allowed). Reset and run again.
- Switch *Accept a change by* to **Critic's score**. Run again, then **Test on reserved cases**.
- Confirm in: **Training vs reserved**. Did the best version get better on cases it never saw?
"""

ui.page("Evaluation Lab: is the new version really better?", GUIDE)
DEFAULT_CRITIC_PROMPT = (agents.HERE / "critic_prompt.md").read_text(encoding="utf-8")


def model_or_error():
    try:
        return ui.get_model()
    except ValueError as error:
        st.error(str(error))
        return None


compare_tab, loop_tab = st.tabs(["1 · Compare A and B", "2 · Let the agents improve the agent"])


# 1 · Compare A and B ------------------------------------------------------------------------------


def show_decision(results: list[suite.RunResult], baseline: str, candidate: str) -> None:
    decision = suite.load_starter("decision")
    common = [case for case in dict.fromkeys(r.case for r in results)
              if {baseline, candidate} <= {r.version for r in results if r.case == case}]
    comparisons = []
    for case in common:
        base = [r for r in results if r.case == case and r.version == baseline]
        cand = [r for r in results if r.case == case and r.version == candidate]
        comparisons.append(decision.CaseComparison(case, sum(r.passed for r in base), len(base), sum(r.passed for r in cand), len(cand)))
    tokens = {name: [r.tokens for r in results if r.version == name and r.case in common] for name in (baseline, candidate)}
    try:
        verdict = decision.decide(comparisons, sum(tokens[baseline]) / len(tokens[baseline]), sum(tokens[candidate]) / len(tokens[candidate]))
    except NotImplementedError:
        st.info("Decision: write decide() in starter/decision.py to see it here.")
        return
    text = {True: f"Adopt {candidate}", False: f"Keep {baseline}", None: "Not enough evidence yet"}[verdict.adopt]
    (st.success if verdict.adopt else st.warning if verdict.adopt is None else st.error)(f"**Decision: {text}**")
    for reason in verdict.reasons:
        st.write(f"- {reason}")


with compare_tab:
    st.write("Version **B** is cheaper and looked better in a few incidents. Is it better on every case, every time?")
    available = agents.versions()
    all_cases = suite.cases()
    with st.container(border=True):
        for version in available.values():
            st.caption(f"**{version.name}**: {version.description}")
        if agents.MINE_ERROR:
            st.error(f"starter/my_agent.py does not build yet: {agents.MINE_ERROR}")
        elif "C (yours)" not in available:
            st.caption("**C (yours)**: appears here when you write `build_agent()` in starter/my_agent.py. Reload the page after editing.")
        left, right = st.columns([4, 1])
        picked = left.multiselect("Cases (Sessions 1 and 2, plus your starter/cases/)", list(all_cases), default=list(all_cases), key="cases")
        repetitions = right.number_input("Repetitions", 1, 5, 1, key="repetitions")
        jobs = [(version, case, all_cases[case]) for version in available.values() for case in picked for _ in range(int(repetitions))]
        run_col, clear_col, note_col = st.columns([1, 1, 4])
        if run_col.button("Run " + " and ".join(name[0] for name in available), type="primary", key="run_suite", disabled=not jobs) and (model := model_or_error()):
            bar = st.progress(0.0, text="Running...")
            new = suite.run_many(jobs, model, on_done=lambda done, total: bar.progress(done / total, text=f"{done}/{total} runs"))
            st.session_state.setdefault("s06_results", []).extend(new)
            bar.empty()
        if clear_col.button("Clear", key="clear_suite"):
            st.session_state["s06_results"] = []
        note_col.caption(f"{len(jobs)} runs. Results add up: run again to add repetitions. "
                         "A run passes when the case checks and your trajectory checks pass.")

    results: list[suite.RunResult] = st.session_state.get("s06_results", [])
    if results:
        st.markdown("**Passes per case** (passes/runs)")
        st.dataframe(suite.pass_table(results), hide_index=True, width="stretch")
        names = list(dict.fromkeys(r.version for r in results))
        if len(names) > 2:
            base_col, cand_col = st.columns(2)
            baseline = base_col.selectbox("Baseline", names, index=0, key="baseline")
            candidate = cand_col.selectbox("Candidate", names, index=len(names) - 1, key="candidate")
        else:
            baseline, candidate = agents.A.name, agents.B.name
        if baseline != candidate:
            show_decision(results, baseline, candidate)
        with st.expander("Every run: failed checks, trajectory checks, actions, summary"):
            st.dataframe([{**r.row, "Trajectory": "; ".join(f"{k}: {v}" for k, v in r.trajectory.items()) or "-",
                           "Actions": "; ".join(r.actions) or "-", "Summary": r.summary} for r in results], hide_index=True, width="stretch")
    st.markdown("**Check:** With 1 run per case, which version wins? With 3? Which case does B lose, and why?")


# 2 · Let the agents improve the agent ---------------------------------------------------------------


def delta(value: float, text: str) -> str | None:
    """A metric's change, or None when nothing changed (no green arrow for zero)."""
    return text if abs(value) > 1e-9 else None


def flow() -> None:
    steps = [("1. Run", f"{len(loop.TRAINING)} training cases"), ("2. Critic", "reviews every run"),
             ("3. Proposer", "changes one thing, reads its memory"), ("4. Keep or not", "case checks or critic's score"),
             ("5. Memory", "one lesson per attempt")]
    for column, (title, text) in zip(st.columns(len(steps)), steps):
        with column.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(text)


def show_loop(state: loop.Loop) -> None:
    first_pass = state.attempts[0].train_before if state.attempts else state.best.pass_rate
    first_score = state.attempts[0].score_before if state.attempts else state.best.score
    a, b, c = st.columns(3)
    a.metric("Training pass rate, best version", f"{state.best.pass_rate:.0%}", delta(state.best.pass_rate - first_pass, f"{state.best.pass_rate - first_pass:+.0%} vs start"))
    b.metric("Critic score, best version", f"{state.best.score:.1f} / 5", delta(state.best.score - first_score, f"{state.best.score - first_score:+.1f} vs start"))
    c.metric("Changes kept", f"{sum(x.kept for x in state.attempts)} of {len(state.attempts)}")
    if state.best.score >= 4 and state.best.pass_rate < 0.6:
        st.warning("The critic is satisfied, but most case checks fail. What does the critic see? (describe_run in starter/improver.py)")
    rows = [{"Iteration": 0, "Change": f"start from {state.start.name}", "Result": "", "Training pass rate": f"{first_pass:.0%}",
             "Critic score": f"{first_score:.1f}", "Why": ""}]
    rows += [{"Iteration": x.iteration, "Change": x.change, "Result": "kept" if x.kept else "discarded",
              "Training pass rate": f"{x.train_before:.0%} -> {x.train_after:.0%}", "Critic score": f"{x.score_before:.1f} -> {x.score_after:.1f}",
              "Why": x.reason} for x in state.attempts]
    st.markdown("**Attempts** (each change is compared with the best version so far)")
    st.dataframe(rows, hide_index=True, width="stretch")

    if state.reserved:
        first, best = state.reserved
        if best.version is first.version:
            st.info("No change was kept: the best version is still the start, so there is nothing new to test.")
        st.markdown("**Training vs reserved**")
        a, b = st.columns(2)
        train_start = state.attempts[0].train_before if state.attempts else state.best.pass_rate
        a.metric("Training cases, best version", f"{state.best.pass_rate:.0%}", delta(state.best.pass_rate - train_start, f"{state.best.pass_rate - train_start:+.0%} vs start"))
        b.metric("Reserved cases (never seen), best version", f"{best.pass_rate:.0%}", delta(best.pass_rate - first.pass_rate, f"{best.pass_rate - first.pass_rate:+.0%} vs start"))
        if state.best.pass_rate > train_start and best.pass_rate <= first.pass_rate:
            st.warning("Better on training, not on the cases it never saw: the loop fitted its training set, or pleased the critic.")
        labelled = [replace(r, version=f"Start: {first.version.name}") for r in first.results]
        labelled += [replace(r, version=f"Best: {best.version.name}") for r in best.results]
        st.dataframe(suite.pass_table(labelled), hide_index=True, width="stretch")

    with st.expander(f"Best version so far: {state.best.version.name}" if state.best else "Best version so far"):
        if state.best:
            st.caption(f"verify_recovery: {state.best.version.verify_recovery}")
            st.code(state.best.version.instructions, language=None, wrap_lines=True)
    if state.who:
        st.markdown("**Who did what** in the last run")
        st.dataframe([{"Piece": piece, "Used": {"yours": "yours (starter/improver.py)", "default": "the lab's default", "none": "not written"}[origin]}
                      for piece, origin in state.who.items()], hide_index=True, width="stretch")
    with st.expander("Memory: what the proposer remembers"):
        st.code(state.memory_text(), language=None, wrap_lines=True)
    with st.expander("What the proposer read before the last change"):
        st.code(state.last_message or "Nothing yet.", language=None, wrap_lines=True)
    with st.expander("The critic's last reviews, and what it saw"):
        if state.best and state.best.reviews:
            st.dataframe([{"Case": r.case, "Pass (checks)": r.passed, "Critic score": v.score, "Problem": v.problem, "Hint": v.fix_hint,
                           "What the critic saw": r.description} for r, v in zip(state.best.results, state.best.reviews)], hide_index=True, width="stretch")


with loop_tab:
    st.write("Two more agents improve the incident agent: the **critic** reviews its runs, the **proposer** changes its instructions. "
             "You decide what counts as better.")
    flow()
    st.info("**What to do here**\n"
            "1. Run 3 iterations from B (or your C) with the lab's default critic and proposer. Read each change and why it was kept or discarded.\n"
            "2. Build your own critic, proposer and memory in `starter/improver.py` (AI help allowed). Click Reset and run 3 iterations again. "
            "The table *Who did what* shows which pieces are yours. Do the changes make more sense?\n"
            "3. Reset, choose *Accept a change by: Critic's score*, run 3 iterations, then **Test on reserved cases**. "
            "Did the version that pleased the critic also improve on cases it never saw?")
    state: loop.Loop | None = st.session_state.get("s06_loop")
    with st.container(border=True):
        left, middle, right = st.columns([1, 2, 1])
        start_name = left.radio("Start from", list(agents.versions()), index=1, key="loop_start", disabled=state is not None)
        accept = middle.radio("Accept a change by", ["Case checks (code, your decision.py)", "Critic's score (LLM)"], key="loop_accept", disabled=state is not None)
        repetitions = right.number_input("Repetitions per case", 1, 3, 3, key="loop_reps", disabled=state is not None,
                                         help="Your decide() may need 3 runs per case to accept a change.")
        st.caption(f"Training: {', '.join(loop.TRAINING)}  ·  Reserved for the end: {', '.join(loop.RESERVED)}")
        one, three, test, reset = st.columns(4)
        progress_box = st.empty()

        def progress(text: str) -> None:
            progress_box.info(text)

        run_one = one.button("Run 1 iteration", type="primary", key="loop_one")
        run_three = three.button("Run 3 iterations", key="loop_three")
        iterations = 1 if run_one else 3 if run_three else 0
        if iterations and (model := model_or_error()):
            if state is None:
                state = loop.Loop(agents.versions()[start_name], DEFAULT_CRITIC_PROMPT, "critic" if accept.startswith("Critic") else "checks", int(repetitions))
                st.session_state.s06_loop = state
            try:
                for _ in range(iterations):
                    state.step(model, progress)
            except Exception as error:
                st.error(f"The loop stopped: {error}")
            progress_box.empty()
        if test.button("Test on reserved cases", key="loop_test", disabled=state is None or not state.attempts) and (model := model_or_error()):
            state.test_reserved(model, progress)
            progress_box.empty()
        if reset.button("Reset", key="loop_reset"):
            st.session_state.pop("s06_loop", None)
            st.rerun()
        if state is not None:
            st.caption("Settings are fixed while the loop runs. Reset to change them, or after editing improver.py.")
    if state is not None:
        show_loop(state)
    st.markdown("**Check:** Which changes were kept, and why? Accepting by the critic's score: did the reserved cases improve too?")
