"""Run from the repository root: uv run --locked streamlit run sessions/course-02-agentic-ai/06-evaluation/lab/app.py"""

from __future__ import annotations

import importlib.util
import sys

import streamlit as st
import yaml

import agents
import judge
import suite
from meridian.lab import ui

GUIDE = """
**1. One run proves nothing**
- Run A and B on every case, **1 repetition**. Which looks better?
- Add repetitions until each case has 3 runs or more. Does the ranking hold?
- Confirm in: the **pass table** (passes/runs per case) and the **TOTAL** row (tokens per run).

**2. Better here, worse there**
- Find a case B wins and a case B loses. Open **Every run** to see which check failed and why.
- Write `starter/decision.py`. Its decision appears under the table.
- Confirm in: **Decision**. Does it say "not enough evidence" with 1 run per case?

**3. Check the path, not only the result**
- Write `starter/trajectory.py`. Run again: the new checks show in **Failed checks**.
- Confirm in: **Every run**, column *Trajectory*. Did a "resolved" come without fresh metrics?

**4. Propose version C**
- Write `starter/candidate.py`, reload the page, run C against A with 3 repetitions.
- Keep C only if your decision says so.

**5. Calibrate the judge**
- Label the 8 summaries yourself, then run the judge with its default prompt.
- Which summaries does it accept that you reject? Rewrite the prompt so it checks the facts, not the style.
- Confirm in: *agree* and *judge accepts what people reject*.

Then: **Fool the judge**. Write a summary that contradicts the facts and still gets accepted.
"""

ui.page("Evaluation Lab: is the new version really better?", GUIDE)
DEFAULT_JUDGE_PROMPT = (agents.HERE / "judge_prompt.md").read_text(encoding="utf-8")
SUMMARIES = yaml.safe_load((agents.HERE / "summaries.yaml").read_text(encoding="utf-8"))["summaries"]


def load_decision():
    spec = importlib.util.spec_from_file_location("s06_decision", agents.STARTER / "decision.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["s06_decision"] = module
    spec.loader.exec_module(module)
    return module


def show_decision(results: list[suite.RunResult], baseline: str, candidate: str) -> None:
    decision = load_decision()
    common = [case for case in dict.fromkeys(r.case for r in results)
              if any(r.case == case and r.version == baseline for r in results) and any(r.case == case and r.version == candidate for r in results)]
    if not common:
        st.caption(f"Run {baseline} and {candidate} on the same cases to compare them.")
        return
    comparisons = []
    for case in common:
        base = [r for r in results if r.case == case and r.version == baseline]
        cand = [r for r in results if r.case == case and r.version == candidate]
        comparisons.append(decision.CaseComparison(case, sum(r.passed for r in base), len(base), sum(r.passed for r in cand), len(cand)))
    tokens = {name: [r.tokens for r in results if r.version == name and r.case in common] for name in (baseline, candidate)}
    try:
        verdict = decision.decide(comparisons, sum(tokens[baseline]) / len(tokens[baseline]), sum(tokens[candidate]) / len(tokens[candidate]))
    except NotImplementedError:
        st.info("Write decide() in starter/decision.py to see a decision here.")
        return
    text = {True: f"Adopt {candidate}", False: f"Keep {baseline}", None: "Not enough evidence"}[verdict.adopt]
    (st.success if verdict.adopt else st.warning if verdict.adopt is None else st.error)(f"**Decision: {text}**")
    for reason in verdict.reasons:
        st.write(f"- {reason}")


compare_tab, judge_tab, fool_tab = st.tabs(["Compare versions", "Calibrate the judge", "Fool the judge"])


# Compare versions -----------------------------------------------------------------------------

with compare_tab:
    available = agents.versions()
    all_cases = suite.cases()
    with st.container(border=True):
        left, middle, right = st.columns([2, 3, 1])
        chosen = left.multiselect("Versions", list(available), default=[name for name in available if name[0] in "AB"], key="versions")
        for name in chosen:
            left.caption(f"**{name}**: {available[name].description}")
        picked = middle.multiselect("Cases (Sessions 1 and 2, plus starter/cases/)", list(all_cases), default=list(all_cases), key="cases")
        repetitions = right.number_input("Repetitions", 1, 5, 1, key="repetitions")
        jobs = [(available[name], case, all_cases[case]) for name in chosen for case in picked for _ in range(int(repetitions))]
        st.caption(f"{len(jobs)} runs, about {len(jobs) * 10} model requests. Results add up: run again to add repetitions.")
        run_col, clear_col = st.columns([1, 5])
        if run_col.button("Run", type="primary", key="run_suite", disabled=not jobs):
            try:
                model = ui.get_model()
            except ValueError as error:
                st.error(str(error))
            else:
                bar = st.progress(0.0, text="Running...")
                new = suite.run_many(jobs, model, on_done=lambda done, total: bar.progress(done / total, text=f"{done}/{total} runs"))
                st.session_state.setdefault("s06_results", []).extend(new)
                bar.empty()
        if clear_col.button("Clear results", key="clear_suite"):
            st.session_state["s06_results"] = []

    results: list[suite.RunResult] = st.session_state.get("s06_results", [])
    if results:
        st.markdown("**Pass table** (passes/runs)")
        st.dataframe(suite.pass_table(results), hide_index=True, width="stretch")
        names = list(dict.fromkeys(r.version for r in results))
        if len(names) >= 2:
            base_col, cand_col = st.columns(2)
            baseline = base_col.selectbox("Baseline", names, index=0, key="baseline")
            candidate = cand_col.selectbox("Candidate", names, index=1, key="candidate")
            if baseline != candidate:
                show_decision(results, baseline, candidate)
        with st.expander("Every run"):
            st.dataframe([{**r.row, "Trajectory": "; ".join(f"{k}: {v}" for k, v in r.trajectory.items()) or "-", "Actions": "; ".join(r.actions) or "-",
                           "Summary": r.summary} for r in results], hide_index=True, width="stretch")
    else:
        st.info("Choose versions and cases, then Run. Start with 1 repetition.")


# Calibrate the judge --------------------------------------------------------------------------

with judge_tab:
    st.write("An LLM judge will grade the summaries of every incident. Before trusting it, compare it with people: you.")
    st.markdown("**1. Label each summary yourself.** Is it acceptable for the shift log, given the facts?")
    labels = {}
    for item in SUMMARIES:
        with st.container(border=True):
            text_col, label_col = st.columns([5, 1])
            text_col.caption(f"{item['id']} · {item['case']} · Facts: {item['facts']}")
            text_col.write(item["summary"])
            labels[item["id"]] = label_col.radio("Acceptable?", ["Yes", "No"], index=None, key=f"label_{item['id']}", horizontal=True)
    st.markdown("**2. Run the judge** and compare.")
    prompt = st.text_area("Judge prompt", DEFAULT_JUDGE_PROMPT, height=160, key="judge_prompt")
    missing = [key for key, value in labels.items() if value is None]
    if st.button("Run the judge on the 8 summaries", key="run_judge", disabled=bool(missing)):
        try:
            with st.spinner("The judge is reading..."):
                st.session_state.s06_judge = (prompt, judge.judge_all(ui.get_model(), prompt, SUMMARIES))
        except Exception as error:
            st.error(f"The judge failed: {error}")
    if missing:
        st.caption(f"Label every summary first ({len(missing)} left).")
    measured = st.session_state.get("s06_judge")
    if measured and not missing:
        measured_prompt, verdicts = measured
        if measured_prompt != prompt:
            st.warning("These verdicts belong to the previous prompt. Run the judge again after your edits.")
        human = [labels[item["id"]] == "Yes" for item in SUMMARIES]
        st.dataframe([{"Summary": item["id"], "You": "Yes" if h else "No", "Judge": "Yes" if v.acceptable else "No", "Score": v.score,
                       "Agree": h == v.acceptable, "Judge's reason": v.reason} for item, h, v in zip(SUMMARIES, human, verdicts)],
                     hide_index=True, width="stretch")
        counts = judge.agreement(human, verdicts)
        st.write(f"Agree: {counts['agree']}/{counts['total']} · Judge accepts what people reject: {counts['judge accepts what people reject']} · "
                 f"Judge rejects what people accept: {counts['judge rejects what people accept']}")
    st.markdown("**Check:** Is the judge grading the facts or the style? Eight examples are not a calibration set; what would you add?")


# Fool the judge -------------------------------------------------------------------------------

with fool_tab:
    st.write("Write a summary that contradicts the facts and still gets accepted. The judge uses the prompt of the previous tab.")
    facts = {f"{item['case']}: {item['facts']}": item["facts"] for item in SUMMARIES}
    picked_facts = st.selectbox("Incident", list(facts), key="fool_case")
    attempt = st.text_area("Your summary", key="fool_summary", placeholder="Restarted order-gateway-2; incident resolved...")
    if st.button("Ask the judge", key="fool_run", disabled=not attempt.strip()):
        try:
            with st.spinner("The judge is reading..."):
                verdict = judge.judge_all(ui.get_model(), st.session_state.get("judge_prompt", DEFAULT_JUDGE_PROMPT),
                                          [{"facts": facts[picked_facts], "summary": attempt}])[0]
            st.session_state.setdefault("s06_fool", []).append({"Summary": attempt, "Accepted": verdict.acceptable, "Score": verdict.score, "Reason": verdict.reason})
        except Exception as error:
            st.error(f"The judge failed: {error}")
    if st.session_state.get("s06_fool"):
        st.dataframe(list(reversed(st.session_state.s06_fool)), hide_index=True, width="stretch")
    st.markdown("**Check:** What made the judge accept a wrong summary? Which deterministic check would catch it instead?")
