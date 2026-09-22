"""Session 3 challenge: rank prepared passages by semantic similarity."""

import math
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("Set OPENAI_API_KEY in your local .env file first.")

EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
DOCUMENTS_DIR = (
    Path(__file__).resolve().parents[3]
    / "projects"
    / "course-01-generative-ai"
    / "knowledge-copilot"
    / "data"
    / "documents"
)


@dataclass(frozen=True)
class Passage:
    """A prepared passage and the embedding used to search it."""

    source: str
    text: str
    embedding: list[float]


@dataclass(frozen=True)
class SearchResult:
    """One ranked passage returned by semantic search."""

    source: str
    text: str
    score: float


def load_texts() -> list[tuple[str, str]]:
    """Load the supplied short passages; no automatic chunking is used here."""
    return [
        (path.name, path.read_text(encoding="utf-8"))
        for path in sorted(DOCUMENTS_DIR.glob("*.md"))
    ]


def create_embeddings(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Create vectors for a batch of text inputs."""
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return how similar two embedding vectors are.

    Hint 1: calculate the dot product of the two vectors.
    Hint 2: divide it by the product of the vectors' magnitudes.
    """
    raise NotImplementedError("Implement cosine_similarity.")


def rank_passages(
    passages: list[Passage], query_embedding: list[float], top_k: int = 3
) -> list[SearchResult]:
    """Score every passage and return only the most relevant results.

    Hint 1: create one SearchResult per passage.
    Hint 2: sort by score, highest first, then keep top_k results.
    """
    raise NotImplementedError("Implement rank_passages.")


def main() -> None:
    question = input("Ask a question about the Apollo missions: ").strip()
    if not question:
        raise ValueError("Please enter a question.")

    client = OpenAI()
    source_texts = load_texts()
    embeddings = create_embeddings(client, [text for _, text in source_texts])
    passages = [
        Passage(source=source, text=text, embedding=embedding)
        for (source, text), embedding in zip(source_texts, embeddings, strict=True)
    ]
    query_embedding = create_embeddings(client, [question])[0]

    results = rank_passages(passages, query_embedding)
    print("\nMost relevant passages:\n")
    for result in results:
        print(f"{result.score:.3f}  {result.source}")
        print(f"{result.text.strip()}\n")


if __name__ == "__main__":
    main()
