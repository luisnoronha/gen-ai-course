# Knowledge Copilot

The evolving project for Course 1: Generative AI Fundamentals and Application.

The supplied Streamlit interface lets us validate the user experience from the
start. The AI workflow will be implemented progressively in `src/`: first by
calling Python functions directly, and later through a FastAPI service.

## Run the interface

```bash
uv sync
uv run streamlit run projects/course-01-generative-ai/knowledge-copilot/app.py
```

At this stage, the interface is intentionally not connected to an LLM or a
knowledge base yet.

## Structure

```text
knowledge-copilot/
├── app.py              # Supplied Streamlit interface
├── src/                # Application logic, added during the course
├── data/documents/     # Prepared passages for mini-project 1
├── data/rag-corpus/    # Real documents for mini-project 2
├── data/evaluations/   # RAG evaluation cases
├── tests/              # Automated and manual checks
└── milestones/         # Project briefs and delivery criteria
```
