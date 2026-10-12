"""Exercise LangChain with simulated Groq HTTP responses; no live API calls."""

import contextlib
import io
import json
import unittest
from unittest.mock import patch

import httpx
from langchain_groq import ChatGroq

import main


class GroqCheckTests(unittest.TestCase):
    def run_response(self, status=200, content="A CRM manages customer relationships.", finish="stop"):
        requests = []

        def respond(request):
            requests.append(json.loads(request.content))
            if status != 200:
                return httpx.Response(status, json={"error": {"message": "test-secret", "type": "test_error"}})
            return httpx.Response(200, json={
                "id": "test", "object": "chat.completion", "created": 0,
                "model": main.GROQ_MODEL,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": finish}],
                "usage": {"prompt_tokens": 25, "completion_tokens": 12, "total_tokens": 37},
            })

        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            def build_model(**kwargs):
                return ChatGroq(**kwargs, http_client=client)
            with patch.object(main, "ChatGroq", side_effect=build_model), patch.object(main, "load_dotenv"), patch.dict("os.environ", {"GROQ_API_KEY": "test-secret", "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"}), contextlib.redirect_stdout(io.StringIO()) as output:
                exit_code = main.main()
        return exit_code, output.getvalue(), requests

    def test_real_langchain_serialization(self):
        code, output, requests = self.run_response()
        self.assertEqual(code, 0)
        self.assertIn("Answer: A CRM", output)
        self.assertNotIn("test-secret", output)
        self.assertEqual(len(requests), 1)
        self.assertIn("CRM", requests[0]["messages"][1]["content"])
        self.assertFalse(requests[0]["include_reasoning"])
        self.assertEqual(requests[0]["max_completion_tokens"], 512)

    def test_provider_failures_are_safe_and_not_retried(self):
        for status in (401, 403, 429, 500):
            with self.subTest(status=status):
                code, output, requests = self.run_response(status=status)
                self.assertEqual(code, 1)
                self.assertIn(str(status), output)
                self.assertNotIn("test-secret", output)
                self.assertEqual(len(requests), 1)

    def test_empty_and_truncated_answers_fail(self):
        for content, finish in (("", "stop"), ("partial", "length")):
            with self.subTest(finish=finish):
                code, output, _ = self.run_response(content=content, finish=finish)
                self.assertEqual(code, 1)
                self.assertNotIn("Answer:", output)

    def test_missing_key_never_builds_client(self):
        with patch.object(main, "load_dotenv"), patch.dict("os.environ", {"GROQ_API_KEY": ""}), patch.object(main, "ChatGroq") as model, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main.main(), 1)
        model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
