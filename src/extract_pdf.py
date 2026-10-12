"""Extract one registered PDF locally for review, preserving page citations."""

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone

from langchain_core.documents import Document
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .config import PROJECT_ROOT
from .errors import WBTError


def exclude_personal_passage(texts):
    """Apply the source manifest's specific exclusion on pages 10 and 11."""
    start = "The uploaded resume was inspected."
    end = "Confidence labels used"
    # Stop if the seed changes: never silently export personal text.
    if len(texts) != 11 or texts[9].count(start) != 1 or texts[10].count(end) != 1:
        raise WBTError("The seed PDF changed: review the personal-content exclusion before extracting.")
    cleaned = list(texts)
    prefix = cleaned[9].split(start, 1)[0]
    # Drop the bullet preceding the excluded paragraph, leaving earlier text intact.
    cleaned[9] = prefix.rstrip(" \t\r\n\x7f\u2022")
    cleaned[10] = end + cleaned[10].split(end, 1)[1]
    return cleaned


def read_sources():
    manifest = json.loads((PROJECT_ROOT / "data/sources.json").read_text(encoding="utf-8"))
    return manifest["sources"]


def load_pdf_pages(source_id="wbt-seed-pdf"):
    """Return one LangChain Document per page, with manifest provenance."""
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", source_id):
        raise WBTError("Source IDs must use lowercase letters, numbers, and hyphens.")
    matches = [item for item in read_sources() if item["source_id"] == source_id]
    if len(matches) != 1:
        raise WBTError(f"Expected one source named '{source_id}' in data/sources.json; found {len(matches)}.")
    source = matches[0]
    if source.get("source_type") not in ("seed-pdf", "pdf") or "path" not in source:
        raise WBTError("Select a registered local PDF, not a website source.")
    is_seed = source_id == "wbt-seed-pdf"
    if not is_seed and source.get("exclude_content"):
        raise WBTError("This PDF has content exclusions. Add and review its exclusion rule before extracting.")
    path = (PROJECT_ROOT / source["path"]).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()) or path.suffix.lower() != ".pdf":
        raise WBTError("The PDF path must be a .pdf file within the project.")
    reader = PdfReader(path)
    mode = source.get("extraction_mode", "plain")
    if mode not in ("plain", "layout"):
        raise WBTError("extraction_mode must be plain or layout.")
    if mode == "layout":
        texts = [page.extract_text(extraction_mode="layout", layout_mode_space_vertically=False) or "" for page in reader.pages]
    else:
        texts = [page.extract_text() or "" for page in reader.pages]
    if not texts or any(not text.strip() for text in texts):
        raise WBTError("A page has no extracted text. Inspect the PDF before proceeding.")
    if is_seed:
        texts = exclude_personal_passage(texts)
    extracted_at = datetime.now(timezone.utc).isoformat()
    fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
    documents = []
    for page_number, text in enumerate(texts, start=1):
        # The seed encodes bullets as DEL. Do not assume other PDFs do too.
        text = (text.replace("\x7f", "\u2022") if is_seed else text).strip()
        warnings = ["Extracted text; compare tables, columns, and qualifiers with the PDF."]
        if "\ufffd" in text:
            warnings.append("Unrecognized characters found; review before using this text.")
        documents.append(Document(page_content=text, metadata={
            "source_id": source["source_id"],
            "source_title": source["source_title"],
            "source_type": source["source_type"],
            "origin": source.get("origin", "origin-unrecorded"),
            "source": source["path"],
            "page_number": page_number,
            "total_pages": len(texts),
            "region": source["region"],
            "status": source["status"],
            "prepared_date": source.get("prepared_date"),
            "effective_date": source.get("effective_date"),
            "source_date_label": source.get("source_date_label"),
            "extraction_mode": mode,
            "confidence_note": source["confidence_note"],
            "extracted_at": extracted_at,
            "source_sha256": fingerprint,
            "extraction_review": "pending",
            "personal_content_removed": is_seed and page_number in (10, 11),
            "warnings": warnings,
        }))
    return documents


def load_seed_pages():
    """Keep the original seed-loading entry point for existing callers."""
    return load_pdf_pages("wbt-seed-pdf")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", default="wbt-seed-pdf", help="PDF source_id from data/sources.json")
    parser.add_argument("--list", action="store_true", help="List registered local PDFs without extracting")
    args = parser.parse_args()
    try:
        if args.list:
            for source in read_sources():
                if source.get("source_type") in ("pdf", "seed-pdf"):
                    print(f"{source['source_id']} | {source.get('origin', 'origin-unrecorded')} | {source['region']} | {source['path']}")
            return 0
        documents = load_pdf_pages(args.source_id)
        source = documents[0].metadata
        # Preserve the original output filenames for the seed.
        name = "wbt_seed" if args.source_id == "wbt-seed-pdf" else args.source_id
        output = PROJECT_ROOT / "data/processed"
        output.mkdir(parents=True, exist_ok=True)
        records = [{"page_content": doc.page_content, "metadata": doc.metadata} for doc in documents]
        (output / f"{name}_pages.json").write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        validity = "current validity unconfirmed" if source["status"] == "unverified" else source["status"]
        preview = [f"{source['source_title']} - REVIEW PENDING\nOrigin: {source['origin']}. {validity}. Dates and historical cautions remain as stated in the source.\nTables require comparison with the original PDF.\n"]
        for doc in documents:
            metadata = doc.metadata
            label = f"\n===== PDF PAGE {metadata['page_number']} =====\n"
            if metadata["personal_content_removed"]:
                label += "[Resume-related personal passage omitted; this note is not source text.]\n"
            preview.append(label + doc.page_content)
        (output / f"{name}_preview.txt").write_text("\n".join(preview), encoding="utf-8")
        print(f"Extracted {len(documents)} pages locally. Origin: {source['origin']}; {validity}.")
        if args.source_id == "wbt-seed-pdf":
            print("Personal passage omitted from pages 10-11; confidence guidance preserved.")
            print("Review pages 4-5 for pricing/currencies and page 11 for confidence labels.")
        print(f"Created data/processed/{name}_pages.json and {name}_preview.txt")
        print("Extraction review: pending. No model call was made.")
        return 0
    except (OSError, WBTError, KeyError, StopIteration, PdfReadError) as error:
        print(f"PDF extraction failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
