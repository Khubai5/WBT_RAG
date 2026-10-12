# Additional PDF sources

Place additional authorized WBT PDFs in this folder. Keep the original seed at
`data/WBT_RAG_Knowledge_Base.pdf`; its existing citation path remains valid.

Registered offer scripts in this folder:

- `WBT_47_Heating_Offer_Overview_and_Script.pdf` - £47 heating funnel blueprint/demo sales script.
- `WBT_TBS_297_Offer_Overview_and_Script.pdf` - £297 TBS event-recordings upsell sales script.

Both are WBT-provided and indexed with region `unspecified`. UK examples and GBP
currency do not establish geographic eligibility. Their stated prices, refund
terms, availability, and sales claims still need current-policy confirmation.

Copying a file here does not automatically ingest or verify it. First inspect it
for personal/restricted material and add one entry to the `sources` array in
`data/sources.json`. Use a unique lowercase, hyphenated source ID.

Example only: replace the filename, title, region, and notes with actual facts.
Do not register this entry until you have the corresponding document.

```json
{
  "source_id": "wbt-service-overview",
  "source_title": "WBT Service Overview",
  "source_type": "pdf",
  "path": "data/source_docs/wbt_service_overview.pdf",
  "region": "unspecified",
  "origin": "WBT-provided",
  "status": "unverified",
  "prepared_date": null,
  "effective_date": null,
  "retrieved_at": null,
  "confidence_note": "Awaiting confirmation of currency and company approval.",
  "exclude_content": []
}
```

Use `UK`, `US`, `North America`, `mixed-or-unspecified`, or `unspecified` according
to the document. Do not infer geographic scope from its currency alone. Leave
unknown dates as `null`. If personal material must be omitted, describe it in
`exclude_content`: extraction stops until a reviewed exclusion rule is added.
The existing seed-specific exclusion is not applied to other PDFs.

From the project folder, list registered PDFs:

```powershell
.\.venv\Scripts\python.exe -m src.extract_pdf --list
```

After registering the example document, extract it with:

```powershell
.\.venv\Scripts\python.exe -m src.extract_pdf --source-id wbt-service-overview
```

Outputs: `data/processed/wbt-service-overview_pages.json` and
`data/processed/wbt-service-overview_preview.txt`. Each PDF gets separate outputs.
This stage reads local files only and does not upload them to Groq.

## What the statuses mean

- `unverified`: current accuracy or company approval is not established.
- `historical`: retained as context about a previous offer or process.
- `draft`: proposed content awaiting approval.
- `current-approved`: confirmed as current and approved by the responsible WBT
  owner; record who confirmed it and when in `confidence_note`.

Source status describes the business information. `extraction_review: pending`
describes whether the extracted text has been checked against the PDF. Successful
extraction does not change a source's business status. For the seed, a publication
or preparation date alone cannot confirm that its historical claims are current.
`origin: WBT-provided` records where the file came from; it does not mean every
price, process, or recommendation in it is still in force.
