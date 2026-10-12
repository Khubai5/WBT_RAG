"""Create searchable passages and retain their complete page context."""

import hashlib
import json

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import PROJECT_ROOT
from .extract_pdf import read_sources
from .extract_web import REPORT_PATH
from .errors import WBTError

CHUNK_SIZE = 900
CHUNK_OVERLAP = 200


def load_registered_pages():
    """Use registered PDF pages and only web pages fetched in the latest report."""
    pages = []
    for source in read_sources():
        if source.get("source_type") not in ("pdf", "seed-pdf"):
            continue
        source_id = source["source_id"]
        name = "wbt_seed" if source_id == "wbt-seed-pdf" else source_id
        extracted = PROJECT_ROOT / "data/processed" / f"{name}_pages.json"
        if not extracted.is_file():
            raise WBTError(f"Extract {source_id} first: python -m src.extract_pdf --source-id {source_id}")
        records = json.loads(extracted.read_text(encoding="utf-8"))
        pdf = (PROJECT_ROOT / source["path"]).resolve()
        if not pdf.is_relative_to(PROJECT_ROOT.resolve()):
            raise WBTError("PDF path must remain within the project.")
        fingerprint = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if not records:
            raise WBTError(f"No extracted pages for {source_id}.")
        for number, record in enumerate(records, start=1):
            metadata = record["metadata"]
            if metadata["source_sha256"] != fingerprint:
                raise WBTError(f"{source_id} changed. Extract it again before chunking.")
            for key in ("source_id", "source_title", "source_type", "origin", "region", "status", "confidence_note"):
                if metadata.get(key) != source.get(key):
                    raise WBTError(f"{source_id} metadata changed. Extract it again before chunking.")
            if metadata["page_number"] != number or metadata["total_pages"] != len(records):
                raise WBTError(f"Invalid page sequence for {source_id}.")
            pages.append(Document(page_content=record["page_content"], metadata=metadata))
    if REPORT_PATH.is_file():
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        by_id = {item["source_id"]: item for item in report["sources"]}
        for source in read_sources():
            if source.get("source_type") != "official-webpage":
                continue
            source_id = source["source_id"]
            item = by_id.get(source_id)
            if not item or item.get("result") != "fetched":
                continue
            path = PROJECT_ROOT / "data/processed" / f"{source_id}_pages.json"
            records = json.loads(path.read_text(encoding="utf-8"))
            if len(records) != 1:
                raise WBTError(f"Expected one fetched page for {source_id}.")
            record = records[0]
            meta = record["metadata"]
            for key in ("source_id", "source_type", "origin", "region", "status", "url"):
                if meta.get(key) != source.get(key):
                    raise WBTError(f"{source_id} metadata changed. Fetch it again before chunking.")
            if (meta["source_sha256"] != item.get("source_sha256")
                    or meta["retrieved_at"] != report["retrieved_at"]
                    or meta["page_number"] != 1):
                raise WBTError(f"{source_id} extraction does not match the latest fetch report.")
            pages.append(Document(page_content=record["page_content"], metadata=meta))
    if not pages:
        raise WBTError("No registered source pages are available.")
    return pages


def split_pages(pages):
    """Chunks find relevant text; parent pages preserve surrounding qualifications."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
    )
    chunks, parents = [], []
    for page in pages:
        if not page.page_content.strip():
            raise WBTError("An empty page cannot be chunked.")
        meta = page.metadata
        parent_id = f"{meta['source_id']}:{meta['source_sha256']}:p{meta['page_number']}"
        parents.append({"parent_id": parent_id, "page_content": page.page_content, "metadata": meta})
        # Split each source unit independently so citations stay traceable.
        for part in splitter.split_documents([page]):
            offset = part.metadata["start_index"]
            if offset < 0 or page.page_content[offset:offset + len(part.page_content)] != part.page_content:
                raise WBTError("A chunk could not be traced to its page text.")
            part.metadata.update({
                "parent_id": parent_id,
                "chunk_id": hashlib.sha256(f"{parent_id}:{offset}:{part.page_content}".encode()).hexdigest(),
                "context_policy": "include-parent-page",
            })
            chunks.append({"page_content": part.page_content, "metadata": part.metadata})
    return chunks, parents


def main():
    try:
        chunks, parents = split_pages(load_registered_pages())
        output = PROJECT_ROOT / "data/processed"
        for filename, records in (("chunks.json", chunks), ("parent_pages.json", parents)):
            (output / filename).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        preview = [
            "CHUNK PREVIEW - REVIEW PENDING",
            "Chunks locate relevant text. Later answers must include the complete parent page for context.",
            f"Maximum {CHUNK_SIZE} characters; up to {CHUNK_OVERLAP} characters overlap. These are not token counts.\n",
        ]
        for chunk in chunks:
            meta = chunk["metadata"]
            validity = "current validity unconfirmed" if meta["status"] == "unverified" else meta["status"]
            preview.append(
                f"\n===== {meta['source_id']} | {'URL ' + meta['url'] if meta['source_type'] == 'official-webpage' else 'page ' + str(meta['page_number'])} | offset {meta['start_index']} =====\n"
                f"Origin: {meta['origin']} | {validity} | Region: {meta['region']} | Text review: {meta['extraction_review']}\n"
                f"Source caution: {meta['confidence_note']}\n\n{chunk['page_content']}\n"
            )
        (output / "chunks_preview.txt").write_text("\n".join(preview), encoding="utf-8")
        print(f"Created {len(chunks)} chunks from {len(parents)} source units across {len({p['metadata']['source_id'] for p in parents})} sources.")
        print("Saved chunks.json, parent_pages.json, and chunks_preview.txt in data/processed/.")
        print("Source status and pending extraction reviews preserved. No model call was made.")
        print("Next stage will check the embedding model's token limit before indexing.")
        return 0
    except (OSError, WBTError, KeyError, TypeError) as error:
        print(f"Chunking failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
