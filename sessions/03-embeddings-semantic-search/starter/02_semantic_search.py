"""Session 3 challenge: build and evaluate semantic search without a vector DB."""

import argparse
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
DEFAULT_MIN_SCORE = float(os.getenv("MIN_SIMILARITY", "0.50"))
SESSION_DIR = Path(__file__).resolve().parent.parent
DOCUMENTS_DIR = (
    Path(__file__).resolve().parents[3]
    / "projects"
    / "course-01-generative-ai"
    / "knowledge-copilot"
    / "data"
    / "documents"
)
EVALUATION_CASES_PATH = SESSION_DIR / "test-data" / "search-cases.json"


@dataclass(frozen=True)
class Passage:
    """A prepared passage and the embedding used to search it."""

    source: str
    text: str
    embedding: list[float]


@dataclass(frozen=True)
class SearchResult:
    """One passage ranked by semantic similarity."""

    source: str
    text: str
    score: float


@dataclass(frozen=True)
class SearchOutcome:
    """The ranked evidence and the decision to use it or abstain."""

    has_enough_context: bool
    message: str
    results: list[SearchResult]


@dataclass(frozen=True)
class EvaluationCase:
    """One labelled query used to evaluate retrieval behaviour."""

    question: str
    expected_source: str | None


def load_texts() -> list[tuple[str, str]]:
    """Load the supplied documents; each file is one passage in this session."""
    return [
        (path.name, path.read_text(encoding="utf-8"))
        for path in sorted(DOCUMENTS_DIR.glob("*.md"))
    ]


def load_evaluation_cases() -> list[EvaluationCase]:
    """Load labelled questions without mixing them into the search corpus."""
    raw_cases = json.loads(EVALUATION_CASES_PATH.read_text(encoding="utf-8"))
    return [
        EvaluationCase(
            question=case["question"], expected_source=case["expected_source"]
        )
        for case in raw_cases
    ]


def create_embeddings(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Create vectors for a batch of text inputs."""
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return the cosine similarity between two vectors.

    Requirements:
    - reject vectors with different dimensions;
    - reject empty or zero-magnitude vectors;
    - calculate dot(left, right) / (magnitude(left) * magnitude(right)).
    """
    raise NotImplementedError("Implement cosine_similarity.")


def rank_passages(
    passages: list[Passage], query_embedding: list[float], top_k: int = 3
) -> list[SearchResult]:
    """Score every passage and return the top_k results, highest score first.

    Build one SearchResult per passage, sort all results, and only then keep
    top_k. Reject top_k values smaller than one.
    """
    raise NotImplementedError("Implement rank_passages.")


def decide_search_outcome(
    results: list[SearchResult], min_score: float
) -> SearchOutcome:
    """Decide whether the best result is strong enough to use.

    A top-k search always returns candidates. It does not prove that any
    candidate supports the question. Abstain when there are no results or the
    best score is below min_score. Keep the candidates in the outcome so that
    the decision remains inspectable.
    """
    raise NotImplementedError("Implement decide_search_outcome.")


def search_passages(
    passages: list[Passage],
    query_embedding: list[float],
    top_k: int,
    min_score: float,
) -> SearchOutcome:
    """Run ranking and the evidence decision as one search operation."""
    results = rank_passages(passages, query_embedding, top_k=top_k)
    return decide_search_outcome(results, min_score=min_score)


def evaluate_search(
    client: OpenAI,
    passages: list[Passage],
    cases: list[EvaluationCase],
    top_k: int,
    min_score: float,
) -> None:
    """Report whether each expected source, or expected abstention, is correct."""
    query_embeddings = create_embeddings(client, [case.question for case in cases])
    passed = 0

    for case, query_embedding in zip(cases, query_embeddings, strict=True):
        outcome = search_passages(passages, query_embedding, top_k, min_score)
        returned_sources = {result.source for result in outcome.results}

        if case.expected_source is None:
            case_passed = not outcome.has_enough_context
            expected = "abstain"
        else:
            case_passed = (
                outcome.has_enough_context
                and case.expected_source in returned_sources
            )
            expected = case.expected_source

        passed += int(case_passed)
        status = "PASS" if case_passed else "FAIL"
        best_score = outcome.results[0].score if outcome.results else float("nan")
        print(f"{status}  best={best_score:.3f}  expected={expected}")
        print(f"      {case.question}")

    print(f"\nPassed: {passed}/{len(cases)}")
    print(f"Configuration: top_k={top_k}, min_score={min_score:.2f}")


def print_outcome(outcome: SearchOutcome) -> None:
    """Print the decision first and keep candidate scores visible."""
    print(f"\n{outcome.message}\n")
    for result in outcome.results:
        print(f"{result.score:.3f}  {result.source}")
        print(f"{result.text.strip()}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", help="Question to search for.")
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run all labelled search cases instead of one question.",
    )
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY in your local .env file first.")

    client = OpenAI()
    source_texts = load_texts()
    document_embeddings = create_embeddings(
        client, [text for _, text in source_texts]
    )
    passages = [
        Passage(source=source, text=text, embedding=embedding)
        for (source, text), embedding in zip(
            source_texts, document_embeddings, strict=True
        )
    ]

    if args.evaluate:
        evaluate_search(
            client,
            passages,
            load_evaluation_cases(),
            top_k=args.top_k,
            min_score=args.min_score,
        )
        return

    question = (
        args.query or input("Ask a question about the Apollo missions: ")
    ).strip()
    if not question:
        raise ValueError("Please enter a question.")

    query_embedding = create_embeddings(client, [question])[0]
    outcome = search_passages(
        passages,
        query_embedding,
        top_k=args.top_k,
        min_score=args.min_score,
    )
    print_outcome(outcome)


if __name__ == "__main__":
    main()
