import unittest
from src.errors import WBTError

from src.index import validate_lengths
from src.retrieval import eligible_chunks, keyword_ranking


class FakeTokenizer:
    def __call__(self, text, **kwargs):
        return {"input_ids": list(text.split())}


class FakeModel:
    max_seq_length = 3
    tokenizer = FakeTokenizer()


class SearchSafetyTests(unittest.TestCase):
    def test_oversized_chunk_fails_before_embedding(self):
        chunks = [{"page_content": "one two three four", "metadata": {"source_id": "seed", "page_number": 2}}]
        with self.assertRaisesRegex(WBTError, "seed page 2 has 4 tokens"):
            validate_lengths(FakeModel(), chunks)

    def test_exact_region_filter_never_promotes_unspecified_or_north_america(self):
        chunks = [{"metadata": {"region": region}} for region in ("UK", "US", "unspecified", "North America")]
        self.assertEqual(eligible_chunks(chunks, "US"), [chunks[1]])
        self.assertEqual(eligible_chunks(chunks, "UK"), [chunks[0]])

    def test_exact_price_token_ranks_matching_passage(self):
        chunks = [
            {"page_content": "Historical price: $297", "metadata": {"chunk_id": "dollars"}},
            {"page_content": "Historical price: £297", "metadata": {"chunk_id": "pounds"}},
        ]
        self.assertEqual(keyword_ranking("$297", chunks), ["dollars"])


if __name__ == "__main__":
    unittest.main()
