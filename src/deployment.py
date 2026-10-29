"""Build a complete deployment snapshot, then launch Streamlit without secrets in Git."""

import argparse
import hashlib
import json
import os
import subprocess
import sys

from .config import PROJECT_ROOT
from .errors import WBTError


def run_module(module, *args):
    subprocess.run([sys.executable, "-m", module, *args], cwd=PROJECT_ROOT, check=True)


def require_web_sources():
    """A deployed demo must not silently lose the website evidence in its README."""
    sources = json.loads((PROJECT_ROOT / "data/sources.json").read_text(encoding="utf-8"))["sources"]
    expected = {s["source_id"] for s in sources if s.get("source_type") == "official-webpage"}
    report = json.loads((PROJECT_ROOT / "data/processed/web_fetch_report.json").read_text(encoding="utf-8"))
    fetched = {s["source_id"] for s in report["sources"] if s.get("result") == "fetched"}
    missing = sorted(expected - fetched)
    if missing:
        raise WBTError("Deployment stopped: website sources unavailable: " + ", ".join(missing)
                       + ". Inspect web_fetch_report.json; do not bypass robots or access restrictions.")


def prepare():
    sources = json.loads((PROJECT_ROOT / "data/sources.json").read_text(encoding="utf-8"))["sources"]
    for source in sources:
        if source.get("source_type") in ("pdf", "seed-pdf"):
            run_module("src.extract_pdf", "--source-id", source["source_id"])
    run_module("src.extract_web")
    require_web_sources()
    run_module("src.chunk_documents")
    run_module("src.index")
    run_module("src.evaluate")
    print("Deployment snapshot built and offline evaluation passed. No Groq call was made.", flush=True)


def launch_command(environ):
    key = environ.get("GROQ_API_KEY", "").strip()
    if not key or key == "your_groq_api_key_here":
        raise WBTError("Set GROQ_API_KEY in your host's secret environment settings before starting.")
    try:
        port = int(environ.get("PORT", "8501"))
    except ValueError as error:
        raise WBTError("PORT must be a whole number between 1 and 65535.") from error
    if not 1 <= port <= 65535:
        raise WBTError("PORT must be a whole number between 1 and 65535.")
    return [sys.executable, "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0",
            f"--server.port={port}", "--server.headless=true"]


def verify_snapshot():
    processed = PROJECT_ROOT / "data/processed"
    manifest = json.loads((PROJECT_ROOT / "data/index/manifest.json").read_text(encoding="utf-8"))
    raw = (processed / "chunks.json").read_bytes()
    from .index import MODEL_ID
    if (manifest["model_id"] != MODEL_ID
            or manifest["chunk_sha256"] != hashlib.sha256(raw).hexdigest()
            or manifest["chunk_count"] != len(json.loads(raw))):
        raise WBTError("Deployment snapshot changed. Rebuild the image before starting.")
    if not (processed / "parent_pages.json").is_file() or not (PROJECT_ROOT / "data/index/chroma").is_dir():
        raise WBTError("Deployment snapshot is incomplete. Rebuild the image before starting.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "serve"))
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            prepare()
        else:
            from dotenv import load_dotenv
            load_dotenv(PROJECT_ROOT / ".env")
            command = launch_command(os.environ)
            verify_snapshot()
            os.chdir(PROJECT_ROOT)
            os.execv(sys.executable, command)
    except (OSError, ValueError, KeyError, TypeError, WBTError, subprocess.CalledProcessError) as error:
        print(f"Deployment failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
