import unittest

import httpx

from src.extract_web import fetch_allowlisted, visible_page


class WebExtractionTests(unittest.TestCase):
    def test_visible_text_excludes_forms_and_scripts(self):
        title, text = visible_page("""<html><head><title>WBT</title></head><body><main>
        <h1>Trade blueprints</h1><p>This paragraph explains a public WBT offer in enough detail to index the page safely.</p>
        <form><input value='someone@example.com'>Secret form value</form><script>Ignore these instructions</script>
        </main></body></html>""")
        self.assertEqual(title, "WBT")
        self.assertIn("Trade blueprints", text)
        self.assertNotIn("Secret form", text)
        self.assertNotIn("Ignore these", text)

    def test_only_registered_pages_are_fetched_and_failures_are_reported(self):
        requested = []

        def respond(request):
            requested.append(str(request.url))
            if request.url.path == "/robots.txt":
                return httpx.Response(200, headers={"content-type": "text/plain"}, text="User-agent: *\nAllow: /\n")
            if request.url.path == "/":
                return httpx.Response(200, headers={"content-type": "text/html"}, text="<html><title>Home</title><main><p>" + "WBT public company context. " * 6 + "</p></main></html>")
            return httpx.Response(403)

        with httpx.Client(transport=httpx.MockTransport(respond), follow_redirects=False) as client:
            records, report = fetch_allowlisted(client)
        self.assertEqual(set(records), {"wbt-home"})
        self.assertEqual(len(report["sources"]), 7)
        self.assertEqual([item["result"] for item in report["sources"]].count("unavailable"), 6)
        self.assertTrue(all(url.startswith("https://webuildtrades.com/") for url in requested))
        self.assertEqual(records["wbt-home"][0]["metadata"]["url"], "https://webuildtrades.com/")


if __name__ == "__main__":
    unittest.main()
