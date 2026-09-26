# Session 3 — Embeddings and Semantic Search

This session moves from individual embedding vectors to a search component that
can rank evidence, abstain when evidence is weak, and combine semantic search
with deterministic metadata filters.

Run all commands from the repository root after `uv sync` and creating a local
`.env` file with `OPENAI_API_KEY`.

## 1. Embed the prepared passages

`01_embed_passages.py` is the complete baseline. It confirms that the API and
the supplied Apollo corpus work before the challenges begin.

```bash
uv run python sessions/03-embeddings-semantic-search/starter/01_embed_passages.py
```

The script creates all document embeddings in one request and prints the model,
number of passages, and vector dimensions. There is nothing to implement.

## 2. Build and evaluate semantic search

`02_semantic_search.py` provides document loading, batched API calls, a search
CLI, and labelled evaluation cases. Complete these functions:

- `cosine_similarity` validates and compares two vectors;
- `rank_passages` scores every passage and keeps the best `top_k` results;
- `decide_search_outcome` decides whether to use the candidates or abstain.

Run one question:

```bash
uv run python sessions/03-embeddings-semantic-search/starter/02_semantic_search.py --query "Which mission first drove a vehicle on the Moon?"
```

Run the labelled cases:

```bash
uv run python sessions/03-embeddings-semantic-search/starter/02_semantic_search.py --evaluate
```

Try different decisions rather than accepting the first configuration:

```bash
uv run python sessions/03-embeddings-semantic-search/starter/02_semantic_search.py --evaluate --top-k 1 --min-score 0.55
```

The exercise is complete when:

- mismatched, empty, and zero vectors are rejected clearly;
- results are sorted from highest to lowest similarity;
- `top_k` values below one are rejected;
- low-scoring searches abstain while retaining candidates for inspection;
- the evaluation output makes false matches visible.

What this exercise puts into practice:

- cosine similarity and top-k retrieval;
- the difference between a ranked candidate and supporting evidence;
- corpus-specific threshold calibration;
- repeatable retrieval evaluation instead of checking one convenient query.

## 3. Add Chroma and metadata filters

`03_chroma_filtered_search.py` provides the OpenAI call, persistent Chroma
client, prepared document metadata, and CLI. Complete these functions:

- `build_where_filter` converts optional filters into a Chroma `where` clause;
- `index_documents` writes stable IDs, documents, metadata, and embeddings with
  `upsert`;
- `search_collection` queries Chroma and normalizes its nested response.

Run an unfiltered search:

```bash
uv run python sessions/03-embeddings-semantic-search/starter/03_chroma_filtered_search.py --query "Which mission used a vehicle on the Moon?"
```

Combine semantic meaning with deterministic constraints:

```bash
uv run python sessions/03-embeddings-semantic-search/starter/03_chroma_filtered_search.py --query "Which mission used a vehicle on the Moon?" --mission-type lunar_landing --min-year 1970
```

Reset the local teaching index when needed:

```bash
uv run python sessions/03-embeddings-semantic-search/starter/03_chroma_filtered_search.py --reset-index --query "Which mission was the final lunar mission?"
```

The exercise is complete when:

- running the script repeatedly keeps eight records rather than creating
  duplicates;
- no filter, one filter, and two combined filters produce valid queries;
- Chroma distances are converted back to cosine similarity;
- every result retains its source, text, metadata, and score;
- results below the evidence threshold are not presented as usable context.

What this exercise puts into practice:

- the boundary between an embedding model and a vector database;
- collections, stable identifiers, and idempotent indexing;
- metadata filtering before vector ranking;
- normalization of database output into application-level objects.

## Supplied data

- `test-data/search-cases.md` is the readable classroom checklist.
- `test-data/search-cases.json` drives the exercise 2 evaluation.
- `test-data/apollo-metadata.json` supplies controlled metadata for exercise 3.

Each Markdown file remains one passage in this session. Automatic chunking is
deliberately postponed until the RAG session so that retrieval behaviour can be
studied without changing two variables at once.
