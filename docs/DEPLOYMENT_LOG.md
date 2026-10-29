# WBT RAG deployment log

Date: 29 October 2026. Owner: Khan Khubaib.

## Scope and target

The user requested implementation and documentation together, with study to
follow later. The chosen deployment path is Docker and local Kubernetes using
KIND. An initially considered Render configuration is not part of this change.
No paid service or public deployment was created.

Baseline repository: `Khubai5/WBT_RAG`, default branch `master`, commit
`0e6c648343292ff3dbb0f9993dfa9839dddc56d3`.

## Repository findings

- The active answer provider is Groq, model `openai/gpt-oss-20b`.
- Embeddings use `all-MiniLM-L6-v2` on CPU; retrieval combines Chroma and keyword search.
- Five PDF sources and seven official website pages are registered.
- Generated data and the search index are excluded from Git.
- README referenced `.env.example`, but the template was missing; it is now included.
- Existing provenance, region guards, current-price refusal and citations are preserved.

## Changes prepared

- Docker image definition with a non-root runtime user, CPU-only PyTorch,
  build-time source/index preparation and an HTTP health check.
- Startup validation for API key, port and source snapshot consistency.
- Fail-fast website coverage check and offline evaluation during image build.
- KIND configuration, Namespace, Deployment, ClusterIP Service and health probes.
- One-command deployment script with explicit Kubernetes context, image import,
  secret delivery over stdin, rollout verification and localhost forwarding.
- Secret/build-context exclusions and a deployment study guide.
- Added HTTPX SOCKS support after the execution environment's proxy caused
  HTTP/Groq client initialization to fail. The dependency check passes afterward.

## Validation and observed limits

| Check | Result |
| --- | --- |
| Three focused deployment unit tests | Passed. |
| Full unit-test suite | 36 tests passed after adding SOCKS support; no live Groq calls. |
| Python compilation for added modules/scripts | Passed. |
| Kubernetes YAML parsing | All four YAML files parse with the expected resource kinds. Schema validation against a real API server remains pending. |
| `pip check` | Passed after dependency installation. |
| Extract registered PDFs from a clean checkout | Succeeded for all five PDFs; seed personal-content exclusion preserved. |
| Full source preparation | Stopped at website ingestion: `robots.txt was unavailable; no pages were fetched.` No bypass attempted. |
| Docker/KIND preflight | Stopped: Docker, KIND and kubectl are unavailable in this execution workspace. |
| Image build and live Kubernetes rollout | Not run; requires a Docker/KIND machine and accessible approved sources. |
| Live Groq answer | Not run; no API key is available in this session. |
| Public URL | None; KIND target is local. |

The original repository records 14/14 offline checks on its earlier 132-passage
snapshot. Those results have not been reproduced against a new website snapshot
in this session. Do not treat them as new deployment verification or a measure
of overall answer accuracy.

## Remaining execution steps

1. Run the prepared automation on the machine with Docker, KIND and kubectl.
2. Supply the Groq key at its hidden prompt.
3. Verify that allowed website fetching and the full image build succeed.
4. Confirm rollout and test real questions, citations and memory usage.
5. Record actual image/cluster versions and outcomes here after execution.

No local or public Kubernetes deployment is claimed complete in this log.
