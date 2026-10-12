"""Check source fidelity and exclusion before PDF text is used in retrieval."""

import unittest
from src.errors import WBTError
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src import extract_pdf
from src.extract_pdf import exclude_personal_passage, load_seed_pages


class SeedExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = load_seed_pages()

    def test_pages_and_citation_metadata(self):
        self.assertEqual([doc.metadata["page_number"] for doc in self.docs], list(range(1, 12)))
        for doc in self.docs:
            self.assertTrue(doc.page_content.strip())
            self.assertEqual(doc.metadata["status"], "unverified")
            self.assertEqual(doc.metadata["extraction_review"], "pending")
            self.assertEqual(doc.metadata["source"], "data/WBT_RAG_Knowledge_Base.pdf")

    def test_prices_and_cautions_preserved(self):
        page_four = self.docs[3].page_content
        for value in ("$47", "\u00a3297", "\u00a320,000 per year", "Historical reference", "verify current"):
            self.assertIn(value, page_four)
        self.assertNotIn("\ufffd", page_four)

    def test_personal_material_removed_but_guidance_retained(self):
        text = "\n".join(doc.page_content for doc in self.docs)
        for personal_reference in ("IPRODUCTIONS", "AI Automation Intern", "The uploaded resume", "The resume itself"):
            self.assertNotIn(personal_reference, text)
        self.assertIn("Confidence labels used", self.docs[10].page_content)
        self.assertIn("Unknown / gap", self.docs[10].page_content)
        self.assertIn("13. Source and confidence register", self.docs[9].page_content)

    def test_missing_exclusion_markers_stop_extraction(self):
        with self.assertRaisesRegex(WBTError, "exclusion"):
            exclude_personal_passage(["changed seed"] * 11)


class AdditionalPdfTests(unittest.TestCase):
    def source(self, **changes):
        source = {
            "source_id": "additional-pdf", "source_title": "Test document",
            "source_type": "pdf", "path": "data/source_docs/test.pdf",
            "region": "UK", "status": "draft", "confidence_note": "Test draft",
            "exclude_content": [],
        }
        source.update(changes)
        return source

    def test_new_pdf_keeps_its_metadata_without_seed_redaction(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "data/source_docs/test.pdf"
            pdf.parent.mkdir(parents=True)
            pdf.write_bytes(b"fake PDF; parsing is simulated")
            reader = SimpleNamespace(pages=[Mock(extract_text=Mock(return_value="New UK draft content"))])
            with patch.object(extract_pdf, "PROJECT_ROOT", root), patch.object(extract_pdf, "read_sources", return_value=[self.source()]), patch.object(extract_pdf, "PdfReader", return_value=reader):
                docs = extract_pdf.load_pdf_pages("additional-pdf")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].page_content, "New UK draft content")
        self.assertEqual(docs[0].metadata["status"], "draft")
        self.assertEqual(docs[0].metadata["region"], "UK")
        self.assertFalse(docs[0].metadata["personal_content_removed"])

    def test_unregistered_or_duplicate_source_stops(self):
        for sources in ([], [self.source(), self.source()]):
            with patch.object(extract_pdf, "read_sources", return_value=sources):
                with self.assertRaisesRegex(WBTError, "Expected one source"):
                    extract_pdf.load_pdf_pages("additional-pdf")

    def test_new_exclusions_are_not_silently_ignored(self):
        with patch.object(extract_pdf, "read_sources", return_value=[self.source(exclude_content=["Personal contact details"])]):
            with self.assertRaisesRegex(WBTError, "exclusion rule"):
                extract_pdf.load_pdf_pages("additional-pdf")

    def test_website_cannot_be_loaded_as_pdf(self):
        with patch.object(extract_pdf, "read_sources", return_value=[self.source(source_type="official-webpage")]):
            with self.assertRaisesRegex(WBTError, "registered local PDF"):
                extract_pdf.load_pdf_pages("additional-pdf")

    def test_unsafe_source_id_stops(self):
        with self.assertRaisesRegex(WBTError, "Source IDs"):
            extract_pdf.load_pdf_pages("../../outside")


if __name__ == "__main__":
    unittest.main()
