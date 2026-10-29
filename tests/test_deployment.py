"""Check deployment failures before any network request or paid model call."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.deployment import launch_command, prepare, require_web_sources
from src.errors import WBTError


class DeploymentTests(unittest.TestCase):
    def test_host_port_and_no_secret_in_process_arguments(self):
        command = launch_command({"GROQ_API_KEY": "test-only-secret", "PORT": "10000"})
        self.assertIn("--server.port=10000", command)
        self.assertIn("--server.address=0.0.0.0", command)
        self.assertNotIn("test-only-secret", " ".join(command))

    def test_missing_key_and_invalid_port_stop_startup(self):
        for env in ({}, {"GROQ_API_KEY": "your_groq_api_key_here"},
                    {"GROQ_API_KEY": "test", "PORT": "abc"},
                    {"GROQ_API_KEY": "test", "PORT": "0"},
                    {"GROQ_API_KEY": "test", "PORT": "65536"}):
            with self.subTest(env=env), self.assertRaises(WBTError):
                launch_command(env)

    def test_failed_web_fetch_stops_build_before_indexing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/processed").mkdir(parents=True)
            (root / "data/sources.json").write_text(json.dumps({"sources": [
                {"source_id": "wbt-home", "source_type": "official-webpage"}
            ]}))
            report = root / "data/processed/web_fetch_report.json"
            report.write_text(json.dumps({"sources": [{"source_id": "wbt-home", "result": "unavailable"}]}))
            with patch("src.deployment.PROJECT_ROOT", root), patch("src.deployment.run_module") as run:
                with self.assertRaisesRegex(WBTError, "wbt-home"):
                    prepare()
                run.assert_called_once_with("src.extract_web")
                report.write_text(json.dumps({"sources": [{"source_id": "wbt-home", "result": "fetched"}]}))
                require_web_sources()


if __name__ == "__main__":
    unittest.main()
