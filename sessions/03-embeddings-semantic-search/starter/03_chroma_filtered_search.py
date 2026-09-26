"""Session 3 challenge: index and filter semantic search results with Chroma."""

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
DEFAULT_MIN_SIMILARITY = float(os.getenv("MIN_SIMILARITY", "0.50"))
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SESSION_DIR = Path(__file__).resolve().parent.parent
DOCUMENTS_DIR = (
    PROJECT_ROOT
    / "projects"
    / "course-01-generative-ai"
    / "knowledge-copilot"
    / "data"
    / "documents"
)
METADATA_PATH = SESSION_DIR / "test-data" / "apollo-metadata.json"
CHROMA_PATH = PROJECT_ROOT / ".chroma" / "session-03"
COLLECTION_NAME = "apollo_missions"


@dataclass(frozen=True)
class DocumentRecord:
    """A source document and the metadata stored beside its embedding."""

    source: str
    text: str
    metadata: dict[str, str | int | bool]


@dataclass(frozen=True)
class SearchFilters:
    """Optional deterministic constraints applied before vector ranking."""

    mission_type: str | None = None
    min_year: int | None = None


@dataclass(frozen=True)
class VectorSearchResult:
    """One normalized Chroma result."""

    source: str
    text: str
    metadata: dict[str, Any]
    similarity: float


def load_records() -> list[DocumentRecord]:
    """Join the supplied documents to their prepared metadata."""
    metadata_items = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    metadata_by_source = {item["source"]: item for item in metadata_items}
    records: list[DocumentRecord] = []

    for path in sorted(DOCUMENTS_DIR.glob("*.md")):
        item = metadata_by_source.get(path.name)
        if item is None:
            raise ValueError(f"Missing metadata for {path.name}.")
        metadata = {key: value for key, value in item.items() if key != "source"}
        records.append(
            DocumentRecord(
                source=path.name,
                text=path.read_text(encoding="utf-8"),
                metadata=metadata,
            )
        )

    unknown_sources = set(metadata_by_source) - {record.source for record in records}
    if unknown_sources:
        raise ValueError(
            f"Metadata references unknown files: {sorted(unknown_sources)}"
        )
    return records


def create_embeddings(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Create OpenAI embeddings explicitly instead of hiding them in Chroma."""
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def build_where_filter(filters: SearchFilters) -> dict[str, Any] | None:
    """Translate optional filters into a Chroma where clause.

    Requirements:
    - mission_type uses an equality condition;
    - min_year uses a greater-than-or-equal condition;
    - return None when no filters were supplied;
    - combine multiple conditions with $and.
    """
    raise NotImplementedError("Implement build_where_filter.")


def index_documents(
    collection: Collection,
    records: list[DocumentRecord],
    embeddings: list[list[float]],
) -> None:
    """Upsert documents, embeddings, metadata, and stable IDs into Chroma.

    Use each source filename as its stable ID. Validate that every record has
    exactly one embedding before writing. Upsert must make repeated runs safe.
    """
    raise NotImplementedError("Implement index_documents.")


def search_collection(
    collection: Collection,
    query_embedding: list[float],
    filters: SearchFilters,
    top_k: int,
    min_similarity: float,
) -> list[VectorSearchResult]:
    """Query Chroma and normalize its nested result into typed rows.

    The collection uses cosine distance, so similarity is 1 - distance.
    Include IDs, documents, metadata, and distances in each returned row.
    Discard rows below min_similarity and reject top_k values below one.
    """
    raise NotImplementedError("Implement search_collection.")


def get_collection(reset_index: bool) -> Collection:
    """Open a persistent cosine-distance collection for repeatable runs."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    if reset_index and COLLECTION_NAME in client.list_collections():
        client.delete_collection(COLLECTION_NAME)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=None,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", help="Question to search for.")
    parser.add_argument(
        "--mission-type",
        choices=[
            "preflight",
            "earth_orbit",
            "lunar_orbit",
            "lunar_landing",
            "aborted_lunar_mission",
        ],
    )
    parser.add_argument("--min-year", type=int)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--min-similarity", type=float, default=DEFAULT_MIN_SIMILARITY
    )
    parser.add_argument(
        "--reset-index",
        action="store_true",
        help="Delete and rebuild the local teaching collection.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY in your local .env file first.")

    records = load_records()
    openai_client = OpenAI()
    document_embeddings = create_embeddings(
        openai_client, [record.text for record in records]
    )
    collection = get_collection(reset_index=args.reset_index)
    count_before = collection.count()
    index_documents(collection, records, document_embeddings)
    count_after = collection.count()
    print(f"Indexed records: {count_after} (before upsert: {count_before})")

    question = (
        args.query or input("Ask a question about the Apollo missions: ")
    ).strip()
    if not question:
        raise ValueError("Please enter a question.")

    filters = SearchFilters(
        mission_type=args.mission_type,
        min_year=args.min_year,
    )
    query_embedding = create_embeddings(openai_client, [question])[0]
    results = search_collection(
        collection,
        query_embedding,
        filters=filters,
        top_k=args.top_k,
        min_similarity=args.min_similarity,
    )

    if not results:
        print("\nNo result met the evidence threshold and filters.")
        return

    print("\nSearch results:\n")
    for result in results:
        print(
            f"{result.similarity:.3f}  {result.source}  "
            f"year={result.metadata['year']}  "
            f"type={result.metadata['mission_type']}"
        )
        print(f"{result.text.strip()}\n")


if __name__ == "__main__":
    main()
