"""Check the simple chat without sending anything to Groq."""

import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app import answer_with_references
from src.config import PROJECT_ROOT


class InterfaceTests(unittest.TestCase):
    def test_citations_remain_readable_without_source_panel(self):
        result = {
            "answer": "TBS teaches owners. [1] The website describes WBT. [2]",
            "sources": [
                (1, {"source_title": "Trade Business School", "page_number": 8}),
                (2, {"source_title": "About WBT", "source_type": "official-webpage", "url": "https://webuildtrades.com/about/"}),
            ],
        }
        answer = answer_with_references(result)
        self.assertIn("[Trade Business School, p. 8]", answer)
        self.assertIn("[About WBT](https://webuildtrades.com/about/)", answer)

    def test_chat_and_new_chat(self):
        result = {
            "answer": "TBS teaches trade owners. [1]",
            "sources": [(1, {"source_title": "Trade Business School", "page_number": 1})],
            "model_called": True,
        }
        with patch("src.answer.answer_question", return_value=result) as answer:
            app = AppTest.from_file(PROJECT_ROOT / "app.py").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.button), 1)
            self.assertEqual(app.button[0].label, "New chat")
            self.assertEqual(len(app.chat_input), 1)
            self.assertEqual(len(app.get("expander")), 0)
            app.chat_input[0].set_value("What is TBS?").run()
            answer.assert_called_once_with("What is TBS?")
        self.assertFalse(app.exception)
        self.assertTrue(any("[Trade Business School, p. 1]" in item.value for item in app.markdown))
        app.button[0].click().run()
        self.assertEqual(app.session_state["messages"], [])
        self.assertTrue(any("What would you like to know?" in item.value for item in app.markdown))


if __name__ == "__main__":
    unittest.main()
