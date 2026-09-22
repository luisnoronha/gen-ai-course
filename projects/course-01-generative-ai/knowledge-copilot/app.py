"""Supplied Streamlit interface for the Knowledge Copilot project."""

import streamlit as st


PROJECT_TITLE = "Apollo Mission Copilot"
WELCOME_MESSAGE = (
    "Welcome! This interface is ready. "
    "We will connect it to the Apollo mission knowledge base during the project."
)
PENDING_RESPONSE = (
    "The interface received your message. "
    "The AI workflow will be connected in the first project milestone."
)


def initialise_session_state() -> None:
    """Create the local chat history once per browser session."""
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": WELCOME_MESSAGE}
        ]


def reset_conversation() -> None:
    """Restore the initial local conversation state."""
    st.session_state.messages = [{"role": "assistant", "content": WELCOME_MESSAGE}]


def render_message(role: str, content: str) -> None:
    """Render one chat message using Streamlit's chat components."""
    with st.chat_message(role):
        st.markdown(content)


def main() -> None:
    st.set_page_config(page_title=PROJECT_TITLE, page_icon="💡", layout="centered")
    initialise_session_state()

    with st.sidebar:
        st.header("Project status")
        st.caption("Interface ready · AI workflow pending")
        st.button("Reset conversation", on_click=reset_conversation)

    st.title(PROJECT_TITLE)
    st.caption("An Apollo mission knowledge assistant built progressively across Course 1.")

    for message in st.session_state.messages:
        render_message(message["role"], message["content"])

    prompt = st.chat_input("Ask a question about the Apollo missions")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    render_message("user", prompt)

    st.session_state.messages.append(
        {"role": "assistant", "content": PENDING_RESPONSE}
    )
    render_message("assistant", PENDING_RESPONSE)


if __name__ == "__main__":
    main()
