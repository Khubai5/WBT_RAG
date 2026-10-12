import unittest

from src.chunk_documents import CHUNK_SIZE, load_registered_pages, split_pages


class ChunkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = load_registered_pages()
        cls.chunks, cls.parents = split_pages(cls.pages)

    def test_every_page_kept_as_context(self):
        self.assertEqual(len(self.parents), len(self.pages))
        self.assertEqual({c['metadata']['parent_id'] for c in self.chunks}, {p['parent_id'] for p in self.parents})
        for original, parent in zip(self.pages, self.parents):
            self.assertEqual(original.page_content, parent['page_content'])

    def test_chunks_have_exact_source_text_and_metadata(self):
        parents = {p['parent_id']: p for p in self.parents}
        for chunk in self.chunks:
            meta = chunk['metadata']
            parent = parents[meta['parent_id']]
            start = meta['start_index']
            self.assertTrue(0 < len(chunk['page_content']) <= CHUNK_SIZE)
            self.assertEqual(chunk['page_content'], parent['page_content'][start:start + len(chunk['page_content'])])
            for key in ('source_id', 'page_number', 'status', 'region', 'confidence_note', 'extraction_review'):
                self.assertEqual(meta[key], parent['metadata'][key])

    def test_ids_are_unique_and_repeatable(self):
        again, _ = split_pages(self.pages)
        ids = [c['metadata']['chunk_id'] for c in self.chunks]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, [c['metadata']['chunk_id'] for c in again])

    def test_prices_retain_full_page_cautions(self):
        seed_price_page = next(p for p in self.parents if p['metadata']['source_id'] == 'wbt-seed-pdf' and p['metadata']['page_number'] == 4)
        for phrase in ('$47', '\u00a3297', 'Historical reference', 'verify current'):
            self.assertIn(phrase, seed_price_page['page_content'])
        self.assertTrue(all(c['metadata']['context_policy'] == 'include-parent-page' for c in self.chunks))


if __name__ == '__main__':
    unittest.main()
