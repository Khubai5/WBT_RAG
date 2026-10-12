"""Fetch only registered public WBT pages after checking robots.txt."""

import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import httpx

from .config import PROJECT_ROOT
from .errors import WBTError
from .extract_pdf import read_sources


USER_AGENT = "WBT-RAG-MVP/0.1"
OUTPUT = PROJECT_ROOT / "data/processed"
REPORT_PATH = OUTPUT / "web_fetch_report.json"
MAX_HTML_BYTES = 2_000_000


def visible_page(html):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else "Untitled page"
    body = soup.select_one("main") or soup.body
    if body is None:
        raise WBTError("No HTML body was found.")
    for element in body.select("script, style, noscript, nav, header, footer, form, iframe, svg, template"):
        element.decompose()
    lines = [re.sub(r"\s+", " ", line).strip() for line in body.get_text("\n").splitlines()]
    text = "\n".join(line for line in lines if line)
    if len(text) < 80:
        raise WBTError("The visible page text is too short to index.")
    return title, text


def fetch_allowlisted(client):
    manifest = json.loads((PROJECT_ROOT / "data/sources.json").read_text(encoding="utf-8"))
    config = manifest["web_ingestion"]
    if not config.get("respect_robots") or config.get("follow_discovered_links"):
        raise WBTError("Web ingestion must respect robots and must not follow discovered links.")
    robots_url = config["robots_url"]
    robots = client.get(robots_url)
    if robots.status_code != 200 or "text/plain" not in robots.headers.get("content-type", ""):
        raise WBTError("robots.txt was unavailable; no pages were fetched.")
    rules = RobotFileParser()
    rules.parse(robots.text.splitlines())
    retrieved_at = datetime.now(timezone.utc).isoformat()
    records = {}
    report = {"retrieved_at": retrieved_at, "robots_url": robots_url, "sources": []}
    for source in manifest["sources"]:
        if source.get("source_type") != "official-webpage":
            continue
        url = source["url"]
        item = {"source_id": source["source_id"], "url": url}
        if not rules.can_fetch(USER_AGENT, url):
            item["result"] = "robots-disallowed"
            report["sources"].append(item)
            continue
        try:
            response = client.get(url)
        except httpx.RequestError:
            item["result"] = "request-failed"
            report["sources"].append(item)
            continue
        item["http_status"] = response.status_code
        if response.status_code != 200:
            item["result"] = "redirect-not-followed" if response.is_redirect else "unavailable"
            report["sources"].append(item)
            continue
        requested, final = httpx.URL(url), response.url
        if requested.host != final.host or requested.path.rstrip("/") != final.path.rstrip("/"):
            item["result"] = "redirected-outside-allowlist"
            report["sources"].append(item)
            continue
        if "text/html" not in response.headers.get("content-type", "") or len(response.content) > MAX_HTML_BYTES:
            item["result"] = "unsupported-content"
            report["sources"].append(item)
            continue
        try:
            page_title, text = visible_page(response.text)
        except WBTError:
            item["result"] = "no-usable-text"
            report["sources"].append(item)
            continue
        fingerprint = hashlib.sha256(response.content).hexdigest()
        metadata = {
            "source_id": source["source_id"],
            "source_title": page_title,
            "source_type": "official-webpage",
            "source": url,
            "url": url,
            "page_number": 1,
            "total_pages": 1,
            "region": source["region"],
            "origin": source["origin"],
            "status": source["status"],
            "prepared_date": None,
            "effective_date": source.get("effective_date"),
            "retrieved_at": retrieved_at,
            "confidence_note": source.get("confidence_note", "Public first-party page. Retrieval date does not establish effective date or approval."),
            "source_sha256": fingerprint,
            "extraction_review": "pending",
            "warnings": ["Visible page text only; compare important qualifiers with the live page."],
        }
        records[source["source_id"]] = [{"page_content": text, "metadata": metadata}]
        item.update({"result": "fetched", "source_sha256": fingerprint, "title": page_title, "characters": len(text)})
        report["sources"].append(item)
    return records, report


def main():
    try:
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=False) as client:
            records, report = fetch_allowlisted(client)
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for source_id, pages in records.items():
            (OUTPUT / f"{source_id}_pages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        for item in report["sources"]:
            print(f"{item['source_id']}: {item['result']}" + (f" (HTTP {item['http_status']})" if "http_status" in item else ""))
        print(f"Saved {len(records)} accessible page(s) and data/processed/web_fetch_report.json. No Groq call was made.")
        return 0
    except (httpx.HTTPError, OSError, WBTError, KeyError, TypeError) as error:
        print(f"Web extraction failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
