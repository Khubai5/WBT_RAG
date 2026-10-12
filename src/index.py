"""Build a local Chroma index from registered PDF and website chunks."""

import hashlib
import json

from .config import PROJECT_ROOT
from .errors import WBTError


MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
CHUNKS_PATH = PROJECT_ROOT / "data/processed/chunks.json"
INDEX_DIR = PROJECT_ROOT / "data/index"
MANIFEST_PATH = INDEX_DIR / "manifest.json"
COLLECTION_NAME = "wbt_source_chunks"


def load_chunks():
    if not CHUNKS_PATH.is_file():
        raise WBTError("Run python -m src.chunk_documents first.")
    chunks = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
    if not chunks or len({item["metadata"]["chunk_id"] for item in chunks}) != len(chunks):
        raise WBTError("The chunk file is empty or has duplicate IDs. Rebuild it.")
    return chunks


def chunk_fingerprint():
    return hashlib.sha256(CHUNKS_PATH.read_bytes()).hexdigest()


def count_tokens(model, text):
    """Count untruncated model input, including special tokens."""
    return len(model.tokenizer(text, add_special_tokens=True, truncation=False)["input_ids"])


def validate_lengths(model, chunks):
    limit = model.max_seq_length
    if not isinstance(limit, int) or limit < 1:
        raise WBTError("The embedding model did not report a usable token limit.")
    counts = [count_tokens(model, chunk["page_content"]) for chunk in chunks]
    too_long = [(i, count) for i, count in enumerate(counts) if count > limit]
    if too_long:
        first, count = too_long[0]
        meta = chunks[first]["metadata"]
        raise WBTError(
            f"{len(too_long)} chunks exceed the model's {limit}-token limit. "
            f"First: {meta['source_id']} page {meta['page_number']} has {count} tokens. "
            "Shorten or resplit these chunks before indexing; silent truncation is unsafe."
        )
    return limit, max(counts)


def build_index():
    import chromadb
    from sentence_transformers import SentenceTransformer

    chunks = load_chunks()
    model = SentenceTransformer(MODEL_ID, device="cpu", local_files_only=MANIFEST_PATH.is_file())
    limit, longest = validate_lengths(model, chunks)
    print(f"Token check passed: longest chunk {longest}/{limit} tokens.")

    texts = [chunk["page_content"] for chunk in chunks]
    vectors = model.encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=False)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(INDEX_DIR / "chroma"))
    try:
        client.delete_collection(COLLECTION_NAME)
    except chromadb.errors.NotFoundError:
        pass
    collection = client.create_collection(
        name=COLLECTION_NAME,
        configuration={"hnsw": {"space": "cosine"}},
    )
    collection.add(
        ids=[chunk["metadata"]["chunk_id"] for chunk in chunks],
        embeddings=vectors.tolist(),
        documents=texts,
        metadatas=[{
            "source_id": chunk["metadata"]["source_id"],
            "source_type": chunk["metadata"]["source_type"],
            "url": chunk["metadata"].get("url", ""),
            "origin": chunk["metadata"]["origin"],
            "page_number": chunk["metadata"]["page_number"],
            "region": chunk["metadata"]["region"],
            "status": chunk["metadata"]["status"],
        } for chunk in chunks],
    )
    manifest = {
        "model_id": MODEL_ID,
        "chunk_sha256": chunk_fingerprint(),
        "chunk_count": len(chunks),
        "max_input_tokens": limit,
        "longest_chunk_tokens": longest,
        "source_scope": "registered PDFs and fetched allowlisted WBT pages",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Indexed {collection.count()} source chunks locally in data/index/chroma.")
    print("No Groq call was made. Text review and current-validity checks remain pending.")


def main():
    try:
        build_index()
    except (OSError, WBTError, KeyError, TypeError, RuntimeError) as error:
        print(f"Indexing failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
