import unittest
from unittest.mock import MagicMock
from codemorph.scorer import SemanticScorer
from codemorph.extractor import LLMClient

class TestSemanticScorer(unittest.TestCase):
    def test_llm_similarity_scoring(self):
        # Setup mock LLM Client
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.generate.return_value = " 0.92 " # mock returning raw float response

        scorer = SemanticScorer(llm_client=mock_llm)
        scorer.model = None  # Force LLM fallback path
        score = scorer.compute_similarity("def old(): pass", "def new(): pass")
        
        self.assertEqual(score, 0.92)
        mock_llm.generate.assert_called_once()

    def test_score_clamping(self):
        # Check that scores > 1.0 or < 0.0 are clamped correctly
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.generate.return_value = "1.5"
        
        scorer = SemanticScorer(llm_client=mock_llm)
        scorer.model = None  # Force LLM fallback path
        score = scorer.compute_similarity("def old(): pass", "def new(): pass")
        self.assertEqual(score, 1.0)

        mock_llm.generate.return_value = "-0.2"
        score2 = scorer.compute_similarity("def old(): pass", "def new(): pass")
        self.assertEqual(score2, 0.0)

if __name__ == "__main__":
    unittest.main()
