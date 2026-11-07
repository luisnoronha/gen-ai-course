"""Streamlit components shared by the labs.

Typical app:

    from meridian.lab import ui
    ui.page("Evaluation Lab", GUIDE)
    switches = ui.controls({"Group": {"name": "Label"}})
    model = ui.get_model()
"""

from __future__ import annotations

import os
from typing import Any, Callable

import streamlit as st

from meridian.agent_runtime import default_model

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")


def get_model() -> Any:
    """The model of every run: a test double set by the tests, or the OpenAI model of the .env file."""
    model = st.session_state.get("model")
    if model is not None:
        return model
    model = default_model()  # Loads the repository's .env.
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Add OPENAI_API_KEY to the repository's .env file, then run again.")
    return model


def page(title: str, guide: str, tab_title: str | None = None) -> None:
    """Wide page, title on the left and the 'What to try' guide on the right."""
    st.set_page_config(page_title=tab_title or title, layout="wide")
    title_column, guide_column = st.columns([5, 1], vertical_alignment="center")
    title_column.title(title)
    if guide_column.button("What to try", icon=":material/info:", key="guide", width="stretch"):
        _guide(guide)


@st.dialog("What to try", width="large")
def _guide(text: str) -> None:
    st.markdown(text)


def controls(groups: dict[str, dict[str, str]], caption: str = "They apply to every run.",
             group_captions: dict[str, str] | None = None) -> dict[str, bool]:
    """Toggles in the sidebar, grouped. Returns {name: on}."""
    with st.sidebar:
        st.header("Controls")
        st.caption(caption)
        for group, items in groups.items():
            st.subheader(group)
            if group_captions and group in group_captions:
                st.caption(group_captions[group])
            for name, label in items.items():
                st.toggle(label, key=f"switch_{name}")
    return current_switches(groups)


def current_switches(groups: dict[str, dict[str, str]]) -> dict[str, bool]:
    return {name: bool(st.session_state.get(f"switch_{name}")) for items in groups.values() for name in items}


def switches_label(groups: dict[str, dict[str, str]], switches: dict[str, bool]) -> str:
    labels = {name: label for items in groups.values() for name, label in items.items()}
    on = [labels[name].split(":")[0] for name, value in switches.items() if value]
    return ", ".join(on) if on else "no controls"


def last_two(key: str, render: Callable[[Any], None], empty: str = "Run once, change a control, run again. The last two runs stay side by side.") -> None:
    """Show the last two runs stored under st.session_state[key], side by side."""
    runs = st.session_state.get(key, [])
    if not runs:
        st.caption(empty)
        return
    for column, (number, run) in zip(st.columns(2), list(enumerate(runs, start=1))[-2:]):
        with column:
            st.markdown(f"**Run {number}**")
            render(run)


def remember(key: str, run: Any) -> None:
    st.session_state.setdefault(key, []).append(run)


def timeline(events: list[dict[str, Any]], lanes: bool = True) -> None:
    """Events as one column per agent (lanes) or as a single list."""
    if not events:
        st.write("Nothing happened yet.")
        return
    if not lanes:
        for event in events:
            with st.expander(f"{event['time']} · {event.get('agent', '')} · {event['step']}"):
                st.write(event["detail"])
        return
    agents = list(dict.fromkeys(event["agent"] for event in events))
    for column, agent in zip(st.columns(len(agents)), agents):
        with column:
            st.markdown(f"**{agent}**")
            for event in events:
                if event["agent"] == agent:
                    with st.expander(f"{event['time']} · {event['step']}"):
                        st.write(event["detail"])
