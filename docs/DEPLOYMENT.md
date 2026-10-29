# WBT RAG: Docker and KIND deployment study guide

Prepared for Khan Khubaib — 29 October 2026.

## Current status

Deployment files and an automated local deployment script have been prepared.
This is not yet a verified running Kubernetes deployment. The preparation
workspace has no Docker engine, KIND, or kubectl. The Groq key is also not
available here. Validation results are recorded in `DEPLOYMENT_LOG.md`.

The chosen target is your local KIND environment. Render is not required.
There is no cloud subscription or paid infrastructure in this configuration.
A local URL is not a publicly hosted resume demo URL.

## 1. Understand what each component does

| Component | Job in this project |
| --- | --- |
| Docker | Packages Python, dependencies, source evidence, embedding model and Chroma index into an image. |
| KIND | Runs a local Kubernetes cluster with Docker containers as nodes. |
| Kubernetes Deployment | Maintains one running WBT application replica and replaces a failed container. |
| Kubernetes Service | Provides a stable internal endpoint for the application. |
| Kubernetes Secret | Supplies the Groq API key to the container through an environment variable. |
| Port forwarding | Makes the internal Service available at `127.0.0.1:8501` on the machine running kubectl. |
| Groq | Runs answer generation remotely; this model is not inside the Docker image. |
| MiniLM + Chroma | Embed and retrieve evidence locally inside the application container. |

The build extracts the five registered PDFs, fetches the seven allowlisted
website pages, chunks them, creates embeddings and runs the offline evaluation.
Requests at runtime retrieve passages and send the selected parent pages and
question to Groq. Citation and regional safeguards remain in the original code.

## 2. Files added and why

| File | Purpose |
| --- | --- |
| `Dockerfile` | Builds the application using Python 3.12, CPU PyTorch, a non-root user and a prepared search snapshot. |
| `.dockerignore` | Excludes local environments, secrets, existing generated indexes and documentation from the build context. |
| `.env.example` | Documents the expected secret name without containing a real key. |
| `src/deployment.py` | Provides `prepare` and `serve` actions; fails on missing evidence, invalid configuration or mismatched chunks. |
| `k8s/kind-config.yaml` | Defines a single-node local cluster; enough for the initial demo. |
| `k8s/namespace.yaml` | Separates WBT resources from other practice workloads. |
| `k8s/deployment.yaml` | Defines the container, Secret reference, CPU/memory settings and HTTP probes. |
| `k8s/service.yaml` | Exposes port 8501 within the cluster. |
| `scripts/deploy_kind.py` | Automates the commands below using only Python's standard library. |
| `tests/test_deployment.py` | Checks fail-fast startup and incomplete website evidence handling. |

## 3. Prerequisites on your machine

Install Python 3.10 or newer, Git, Docker, KIND and kubectl. On Windows, Docker
Desktop must run Linux containers. If using your Ubuntu VM, run the commands
inside that VM with a working Docker engine and sufficient free disk and RAM.
Allow several GB of disk for images/dependencies and several GB of RAM for the
cluster and application. Actual memory use still needs measurement.

Run from the repository root:

```powershell
python scripts/deploy_kind.py --check-only
```

Expected result: installed tool versions and `Tools available and Docker is
running. No changes made.` If a tool is missing, the script stops before making
changes. This command does not need the Groq key.

## 4. Automated deployment

```powershell
python scripts/deploy_kind.py
```

Enter the Groq key at the hidden terminal prompt, or supply `GROQ_API_KEY` in
your existing environment. The script does not read your `.env` file or write
the key to a file. Do not paste a key into chat, Git, or a screenshot.

The script builds the image first. Only after a successful build does it create
or reuse the dedicated `wbt-rag` cluster, load the image, apply the resources,
wait for rollout, and start localhost port forwarding.

Expected successful rollout: one Ready pod and a ClusterIP Service. Open
`http://127.0.0.1:8501` on the machine running the script. Keep the terminal
open. If the script runs in an Ubuntu VM, that URL belongs to the VM; open its
browser there or configure an explicit SSH tunnel from your host.

Ctrl+C stops port forwarding. The cluster and application remain running.

## 5. The underlying commands, for later study

Build the image. The final dot means use this directory as the build context.

```powershell
docker build -t wbt-rag:local .
```

This downloads dependencies and the embedding model, then prepares the source
snapshot. No Groq key is needed at build time. The exact passage count can
change with website content. A failed fetch or offline evaluation stops the
build instead of silently shipping fewer sources.

Create the cluster only if it does not already exist, then import the image:

```powershell
kind create cluster --name wbt-rag --config k8s/kind-config.yaml --wait 120s
kind load docker-image wbt-rag:local --name wbt-rag
kubectl --context kind-wbt-rag apply -f k8s/namespace.yaml
```

The automation supplies the Secret next, through JSON on stdin. There is no
committed Secret YAML. Kubernetes Secrets are not inherently encrypted merely
because they use the Secret resource type. Restrict access to this local cluster.
The deployment script uses server-side apply to avoid storing a plaintext key
in the client-side last-applied annotation.

After the Secret exists, apply the workload and wait:

```powershell
kubectl --context kind-wbt-rag apply -f k8s/deployment.yaml -f k8s/service.yaml
kubectl --context kind-wbt-rag -n wbt-rag rollout status deployment/wbt-rag --timeout=300s
kubectl --context kind-wbt-rag -n wbt-rag get pods,svc
kubectl --context kind-wbt-rag -n wbt-rag port-forward --address=127.0.0.1 service/wbt-rag 8501:8501
```

`imagePullPolicy: Never` tells this local deployment to use the image imported
into KIND. There is no registry push. The script restarts the Deployment after
each build/import so repeated deployments use the new local image and key.

## 6. Data, probes and resource choices

The generated index is excluded from Git but created inside the image during
the build. A new container starts from that image snapshot, so no persistent
volume is needed for this read-only source collection. Runtime changes to the
container filesystem are disposable. Refresh sources by rebuilding the image
and deploying again; there is no automatic periodic crawl.

The initial pod requests 250 millicores and 512 MiB, with limits of 2 CPUs and
2 GiB. These are starting settings, not measured guarantees. The embedding model
loads on the first search, so a healthy empty chat does not prove memory is
sufficient for inference. Test a real question and inspect pod state/logs.

Startup, readiness and liveness probes use Streamlit's `/_stcore/health` path.
They verify the HTTP process. They do not establish Groq availability, semantic
answer accuracy or first-query model readiness. The startup launcher also
checks the stored chunks' fingerprint and required index/context paths.

## 7. Verify behavior after deployment

| Check | Expected behavior |
| --- | --- |
| Open the local URL | WBT chat loads without a missing-index message. |
| Ask `What is Trade Business School?` | Answer includes source titles and PDF page citations. |
| Ask `What does the US Electrical Funnel Blueprint page say it includes?` | An answer grounded in US evidence with a website citation, or an explicit insufficient-evidence response. |
| Ask `What is the current UK blueprint price?` | Refuses to establish a current price without approved evidence. |
| Ask `What is the blueprint offer price?` | Requests a UK/US region before retrieval/model use. |
| Click New chat | Clears the current browser session's displayed messages. |
| Restart the pod and ask again | Source snapshot still works; browser chat history is not durable storage. |

The existing 14-case suite checks retrieval and deterministic safeguards, not
overall model accuracy. Its previous 14/14 result must not be described as
100% answer accuracy. Live citations still need claim-by-claim review.

## 8. Diagnose problems

```powershell
kubectl --context kind-wbt-rag -n wbt-rag get pods
kubectl --context kind-wbt-rag -n wbt-rag describe deployment wbt-rag
kubectl --context kind-wbt-rag -n wbt-rag logs deployment/wbt-rag --tail=100
kubectl --context kind-wbt-rag -n wbt-rag get events --sort-by=.lastTimestamp
```

| Symptom | Action |
| --- | --- |
| Docker daemon unavailable | Start Docker Desktop or your VM's Docker engine and repeat preflight. |
| `ErrImageNeverPull` | Load the image into the named cluster; verify the image tag matches the manifest. |
| `CreateContainerConfigError` | Check that `wbt-rag-secrets` exists in namespace `wbt-rag`. Do not dump the Secret's contents. |
| `OOMKilled` | Measure usage and raise local resource allocation/limits if your machine can support it. |
| Build fails fetching WBT pages | Inspect build output and allowed-source fetch results; do not bypass robots/403 restrictions. |
| Build fails downloading MiniLM | Check access to Hugging Face and retry the build; runtime is configured to use the cached model. |
| HTTP 401 from Groq | Replace the key through the deployment script, then redeploy. |
| HTTP 429 from Groq | Wait for the provider limit to reset and check your account limits. |
| Local port 8501 is occupied | Use `kubectl ... port-forward service/wbt-rag 8502:8501` and open localhost port 8502. |

To stop and remove this dedicated demo cluster, when you intentionally want to:

```powershell
kind delete cluster --name wbt-rag
```

That command removes this cluster and its Secret/workloads. It does not remove
your repository or Docker image. Recreate it with the automation when needed.

## 9. Resume explanation and next boundary

After actual successful rollout and a real query check, you can describe this
as a containerized RAG prototype deployed to a local Kubernetes cluster using
KIND. Explain the image build, source preparation, Secret, Deployment, Service,
and probes. Until that check succeeds, describe deployment as prepared.

This setup has no staff login and no public endpoint. A public demo requires a
separate hosting/access decision, API usage controls and deployment validation.
Using KIND does not require Render, and this guide creates no cloud resources.

## References

- KIND quick start: https://kind.sigs.k8s.io/docs/user/quick-start/
- Kubernetes probes: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- Kubernetes Secrets: https://kubernetes.io/docs/concepts/configuration/secret/
