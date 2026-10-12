import unittest

from src.extract_pdf import load_pdf_pages


class OfferSourceTests(unittest.TestCase):
    def test_new_sales_scripts_keep_currency_and_cautions(self):
        for source_id, pages, price in (
            ("wbt-heating-47-offer", 5, "£47"),
            ("tbs-event-297-offer", 4, "£297"),
        ):
            with self.subTest(source_id=source_id):
                documents = load_pdf_pages(source_id)
                self.assertEqual(len(documents), pages)
                self.assertIn(price, documents[0].page_content)
                self.assertNotIn("\ufffd", "".join(doc.page_content for doc in documents))
                self.assertEqual(documents[0].metadata["origin"], "WBT-provided")
                self.assertEqual(documents[0].metadata["region"], "unspecified")
                self.assertEqual(documents[0].metadata["status"], "unverified")
                self.assertIsNone(documents[0].metadata["effective_date"])


if __name__ == "__main__":
    unittest.main()
