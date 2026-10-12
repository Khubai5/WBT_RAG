"""Search registered source passages using local vectors and exact words."""

import argparse
from collections import Counter
from functools import lru_cache
import json
import math
import re
import sys

from .index import (
    COLLECTION_NAME, INDEX_DIR, MANIFEST_PATH,
    MODEL_ID, chunk_fingerprint, count_tokens, load_chunks,
)
from .errors import WBTError


REGIONS = ("all", "UK", "US", "North America", "unspecified", "mixed-or-unspecified")


@lru_cache(maxsize=1)
def embedding_model():
    """Reuse the CPU model across questions in the same local app process."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_ID, device="cpu", local_files_only=True)


def eligible_chunks(chunks, region):
    if region not in REGIONS:
        raise WBTError(f"Region must be one of: {', '.join(REGIONS)}")
    return [item for item in chunks if region == "all" or item["metadata"]["region"] == region]


def words(text):
    return re.findall(r"[a-z0-9]+|[$£]\d+(?:\.\d+)?", text.lower())


def keyword_ranking(question, chunks):
    """Small BM25-style ranking; no downloaded keyword model is needed."""
    terms = set(words(question))
    if not terms:
        return []
    docs = [Counter(words(item["page_content"])) for item in chunks]
    lengths = [sum(counts.values()) for counts in docs]
    average_length = sum(lengths) / max(len(lengths), 1)
    frequencies = {term: sum(term in counts for counts in docs) for term in terms}
    ranked = []
    for chunk, counts, length in zip(chunks, docs, lengths):
        score = 0.0
        for term in terms:
            if not counts[term]:
                continue
            idf = math.log(1 + (len(chunks) - frequencies[term] + 0.5) / (frequencies[term] + 0.5))
            score += idf * counts[term] * 2.2 / (counts[term] + 1.2 * (0.25 + 0.75 * length / average_length))
        if score:
            ranked.append((score, chunk["metadata"]["chunk_id"]))
    return [chunk_id for _, chunk_id in sorted(ranked, reverse=True)]


def fuse_rankings(vector_ids, keyword_ids):
    scores = Counter()
    for ranking in (vector_ids, keyword_ids):
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] += 1 / (60 + rank)
    return [chunk_id for chunk_id, _ in scores.most_common()]


def search(question, region="all", limit=3):
    import chromadb

    if not question.strip():
        raise WBTError("Enter a question.")
    if not MANIFEST_PATH.is_file():
        raise WBTError("Run python -m src.index first.")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest["model_id"] != MODEL_ID or manifest["chunk_sha256"] != chunk_fingerprint():
        raise WBTError("The chunks or embedding model changed. Rebuild with python -m src.index.")
    chunks = load_chunks()
    if len(chunks) != manifest["chunk_count"]:
        raise WBTError("The chunk count changed. Rebuild the index.")

    client = chromadb.PersistentClient(path=str(INDEX_DIR / "chroma"))
    collection = client.get_collection(COLLECTION_NAME)
    if collection.count() != len(chunks):
        raise WBTError("The stored index is incomplete. Rebuild with python -m src.index.")
    eligible = eligible_chunks(chunks, region)
    if not eligible:
        return []

    model = embedding_model()
    if count_tokens(model, question) > model.max_seq_length:
        raise WBTError("Question exceeds the embedding model's token limit. Shorten it.")
    vector = model.encode([question], normalize_embeddings=True, show_progress_bar=False)[0].tolist()
    result = collection.query(
        query_embeddings=[vector], n_results=min(20, len(eligible)),
        where=None if region == "all" else {"region": region},
        include=["metadatas"],
    )
    vector_ids = result["ids"][0]
    keyword_ids = keyword_ranking(question, eligible)
    by_id = {item["metadata"]["chunk_id"]: item for item in eligible}
    return [by_id[chunk_id] for chunk_id in fuse_rankings(vector_ids, keyword_ids)[:limit]]


def main():
    # Windows PowerShell may use cp1252, which cannot print some PDF symbols.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Search the local WBT source index; does not call Groq.")
    parser.add_argument("question", help="A question or search phrase")
    parser.add_argument("--region", choices=REGIONS, default="all")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 10:
        parser.error("--limit must be between 1 and 10")
    try:
        matches = search(args.question, args.region, args.limit)
    except (OSError, WBTError, KeyError, TypeError, RuntimeError) as error:
        parser.exit(1, f"Search failed: {error}\n")
    if not matches:
        print(f"No indexed source passage has region '{args.region}'. No answer is established.")
        return
    for number, match in enumerate(matches, start=1):
        meta = match["metadata"]
        location = meta["url"] if meta["source_type"] == "official-webpage" else f"page {meta['page_number']}"
        print(f"\n{number}. {meta['source_title']}, {location}")
        validity = "current and approved" if meta["status"] == "current-approved" else "current validity unconfirmed"
        print(f"Origin: {meta['origin']} | Region: {meta['region']} | {validity} | Text review: {meta['extraction_review']}")
        print(f"Caution: {meta['confidence_note']}")
        print(match["page_content"].replace("\n", " "))
    print("\nSearch only; no Groq call was made.")


if __name__ == "__main__":
    main()
