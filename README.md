# We Build Trades RAG Assistant

This is the first local prototype for a future WBT staff product. It searches five
WBT-provided PDFs and seven selected pages of the official website, then sends
the question and selected evidence to Groq for a cited answer. Embeddings and
the Chroma search index run locally. The source register is
[`data/sources.json`](data/sources.json); [`data/source_links.md`](data/source_links.md)
is a link list, not answer evidence. The [stage-by-stage PDF guide](docs/WBT_RAG_Stage_Guide.pdf)
explains each completed stage.

## Run the prototype in PowerShell

For the Docker and local Kubernetes deployment, see
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). From a machine with Docker, KIND,
kubectl and Python installed, run `python scripts/deploy_kind.py`. It builds the
source snapshot, prompts for the Groq key privately, deploys to a dedicated
KIND cluster and starts localhost port forwarding. This is a local deployment;
it does not create a public URL. See [`docs/DEPLOYMENT_LOG.md`](docs/DEPLOYMENT_LOG.md)
for actual validation status.

From `H:\WBT_RAG`, with Python and a Groq key already configured in `.env`:

```powershell
Set-Location H:\WBT_RAG
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.extract_web
.\.venv\Scripts\python.exe -m src.chunk_documents
.\.venv\Scripts\python.exe -m src.index
.\.venv\Scripts\python.exe -m src.evaluate
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Expected on the tested source snapshot: seven website pages fetched, 132 passages
indexed, 14/14 offline checks passed, unit tests `OK`, and the app at
`http://localhost:8501`. Page content and passage counts may change when the
website changes. Stop the app with Ctrl+C. To inspect fetch results, run
`notepad .\data\processed\web_fetch_report.json`.

If Chrome says `localhost refused to connect`, use the address Streamlit prints
(`http://127.0.0.1:8501`) and keep the PowerShell window running. The project
`.streamlit/config.toml` disables optional usage-statistics collection; this
avoids a Windows profile write error in restricted environments.
If the page opens but a Groq question says it cannot connect, start Streamlit
from your own PowerShell terminal rather than an IDE/tool sandbox that blocks
outbound network traffic. A direct `python -m src.answer "What is Trade Business School?"`
check can distinguish network access from a browser issue.

Type `What is Trade Business School?` in the chat field and press Enter. Expect
a brief answer with PDF titles and pages inline. Ask `What does the US Electrical
Funnel Blueprint page say it includes?` to see an inline official-page link.
Ask about a *current* blueprint price: the app should say that approved current
pricing is not established and make no Groq call. An offer question without a
region asks you to name UK or US in your message. **New chat** clears the local
conversation display. Each question is currently searched on its own; earlier
messages are not sent back to Groq as conversation context.

## How this stage works

`src/extract_web.py` checks robots.txt and visits only the seven URLs already
registered in `data/sources.json`; it does not follow page links or redirects.
It removes scripts, forms, and navigation, then records source URL, region,
retrieval time, and fetch status. The PDFs retain title and page provenance.
`src/chunk_documents.py` splits each source into searchable passages while
keeping the complete page as citation context. `src/index.py` stores local
embeddings. `src/retrieval.py` combines meaning-based and exact-word search.
`src/answer.py` sends only selected pages and the question to Groq, asks for
cited answers, and refuses unsupported current-price claims. `app.py` shows
those citations inline with each chat answer.

The successful fetch on 12 October 2026 returned all seven pages, including
separate UK and US blueprints. Earlier requests saw HTTP 403, so a future fetch
may report some pages as unavailable. The fetch report controls which website
pages enter a rebuilt index; it will not silently use stale page files.

WBT-provided origin and public website origin do not establish current business
approval. PDF text extraction still needs visual review. The first live Groq
checks produced PDF and US-page citations, but human claim-by-claim review is
needed before staff reliance. Prices, guarantees, and offer eligibility require
approved current source material. The local app has no staff login or team
hosting. See [`eval/REVIEW.md`](eval/REVIEW.md) for remaining checks.

## Current interface stage

The interface uses a quiet light background with WBT teal accents. It has one
chat field and a **New chat** control. Source cards, search buttons, and the
region selector were removed; source titles/pages or website links remain
inline with answers so claims can still be checked. `src/errors.py` defines `WBTError`
for expected setup and source-validation problems; those checks still stop
stale citations or missing configuration. The interface shows their messages
without a Python traceback. No retrieved content or index format changed in
this stage.

To check this stage, restart the running Streamlit server with Ctrl+C and the
launch command above. Expect the new branded layout at `127.0.0.1:8501`.
The offline suite currently passes 14/14 checks and 33 unit tests.

To add a PDF, put it in `data/source_docs/`, register it in `data/sources.json`,
and follow [`data/source_docs/README.md`](data/source_docs/README.md). Keep
`.env` private. Rebuild the guide with
`.\.venv\Scripts\python.exe -m src.build_stage_guide`.
