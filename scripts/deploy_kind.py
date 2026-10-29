"""Deploy to the dedicated local KIND cluster; Python 3.10+ and no pip packages needed."""

import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
CLUSTER = "wbt-rag"
CONTEXT = "kind-wbt-rag"


def run(*args, capture=False, input_text=None):
    return subprocess.run(args, cwd=ROOT, check=True, text=True, input=input_text,
                          stdout=subprocess.PIPE if capture else None)


def kubectl(*args, **kwargs):
    return run("kubectl", "--context", CONTEXT, *args, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Check tools without changing anything")
    args = parser.parse_args()
    try:
        missing = [tool for tool in ("docker", "kind", "kubectl") if not shutil.which(tool)]
        if missing:
            raise RuntimeError("Install or add to PATH: " + ", ".join(missing))
        run("docker", "info", capture=True)
        run("kind", "version")
        run("kubectl", "version", "--client=true")
        if args.check_only:
            print("Tools available and Docker is running. No changes made.")
            return 0
        key = os.environ.get("GROQ_API_KEY", "").strip()
        if not key:
            key = getpass.getpass("Groq API key (hidden; never saved to Git): ").strip()
        if not key or key == "your_groq_api_key_here":
            raise RuntimeError("A Groq API key is required. No cluster changes made.")
        # Build before cluster mutation. A failed source fetch or evaluation stops here.
        run("docker", "build", "--tag", "wbt-rag:local", ".")
        clusters = run("kind", "get", "clusters", capture=True).stdout.splitlines()
        if CLUSTER not in clusters:
            run("kind", "create", "cluster", "--name", CLUSTER,
                "--config", "k8s/kind-config.yaml", "--wait", "120s")
        run("kind", "load", "docker-image", "wbt-rag:local", "--name", CLUSTER)
        kubectl("apply", "-f", "k8s/namespace.yaml")
        secret = {"apiVersion": "v1", "kind": "Secret", "type": "Opaque",
                  "metadata": {"name": "wbt-rag-secrets", "namespace": "wbt-rag"},
                  "stringData": {"GROQ_API_KEY": key}}
        # Server-side apply avoids recording plaintext in the last-applied annotation.
        # The key is passed only on stdin, never in CLI arguments or a file.
        kubectl("apply", "--server-side", "--field-manager=wbt-kind-deploy", "-f", "-",
                input_text=json.dumps(secret), capture=True)
        kubectl("apply", "-f", "k8s/deployment.yaml", "-f", "k8s/service.yaml")
        # Reload the freshly imported local image, including on repeated deployments.
        kubectl("-n", "wbt-rag", "rollout", "restart", "deployment/wbt-rag")
        kubectl("-n", "wbt-rag", "rollout", "status", "deployment/wbt-rag", "--timeout=300s")
        kubectl("-n", "wbt-rag", "get", "pods,svc")
        print("Deployment ready. Open http://127.0.0.1:8501 after the next command starts.")
        print("Keep this terminal open. Ctrl+C stops port-forwarding; the cluster keeps running.")
        kubectl("-n", "wbt-rag", "port-forward", "--address=127.0.0.1", "service/wbt-rag", "8501:8501")
    except KeyboardInterrupt:
        print("\nPort-forwarding stopped.")
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"KIND deployment stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
