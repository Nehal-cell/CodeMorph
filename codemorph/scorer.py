import re
import logging
import numpy as np
from typing import Optional
from codemorph.extractor import LLMClient

logger = logging.getLogger(__name__)

# Try to import sentence-transformers
HAS_SENTENCE_TRANSFORMERS = False
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    logger.warning("sentence-transformers not installed. Falling back to LLM-based semantic scoring.")

class SemanticScorer:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        self.model = None
        
        if HAS_SENTENCE_TRANSFORMERS:
            try:
                # Load a lightweight, fast model
                logger.info("Initializing local SentenceTransformer model (all-MiniLM-L6-v2)...")
                self.model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception as e:
                logger.error(f"Failed to load SentenceTransformer: {e}. Falling back to LLM.")
                self.model = None

    def compute_similarity(self, original_code: str, migrated_code: str) -> float:
        """Computes a semantic equivalence score between original and migrated code."""
        if not original_code or not migrated_code:
            return 0.0

        if self.model is not None:
            try:
                return self._compute_local_similarity(original_code, migrated_code)
            except Exception as e:
                logger.error(f"Local similarity scoring failed: {e}. Retrying with LLM fallback.")
                return self._compute_llm_similarity(original_code, migrated_code)
        else:
            return self._compute_llm_similarity(original_code, migrated_code)

    def _compute_local_similarity(self, original_code: str, migrated_code: str) -> float:
        """Uses sentence-transformers to embed LLM-generated summaries and calculates cosine similarity."""
        # 1. Generate summaries first using LLM
        summary_prompt = "Generate a concise 1-sentence summary of the business logic of this python code:\n\n"
        
        orig_summary = self.llm.generate(summary_prompt + original_code)
        mig_summary = self.llm.generate(summary_prompt + migrated_code)
        
        # 2. Embed summaries
        embeddings = self.model.encode([orig_summary, mig_summary])
        
        # 3. Calculate cosine similarity
        emb1, emb2 = embeddings[0], embeddings[1]
        dot_product = np.dot(emb1, emb2)
        norm_a = np.linalg.norm(emb1)
        norm_b = np.linalg.norm(emb2)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot_product / (norm_a * norm_b))

    def _compute_llm_similarity(self, original_code: str, migrated_code: str) -> float:
        """Uses LLM to grade semantic equivalence between 0.0 and 1.0."""
        prompt = f"""You are a professional code auditor. Compare these two versions of a Python component:

--- ORIGINAL VERSION ---
```python
{original_code}
```

--- MIGRATED VERSION ---
```python
{migrated_code}
```

Evaluate the semantic equivalence of their business logic (e.g. whether they perform the same behavior, handle input/output contracts similarly, and execute equivalent steps, despite using different framework syntax).
Rate this semantic equivalence on a scale from 0.0 (completely different/broken) to 1.0 (perfectly equivalent).

Output ONLY the final numeric score (e.g., 0.95 or 0.88) as a raw float. Do not include any explanations, markdown code blocks, or extra text.
"""
        try:
            response = self.llm.generate(prompt).strip()
            # Clean up potential markdown formatting
            if response.startswith("```"):
                response = response.split("\n")[1] if "\n" in response else response.replace("`", "")
            response = response.replace("`", "").strip()
            
            # Extract first float (with optional negative sign) or single digit from the response
            match = re.search(r"-?\d+\.\d+|\b[01]\b", response)
            if match:
                score = float(match.group(0))
            else:
                score = float(response)
            
            # Clip score between 0.0 and 1.0
            return max(0.0, min(1.0, score))
        except Exception as e:
            logger.error(f"LLM similarity scoring failed to parse response ({response}): {e}")
            return 0.5 # Safe average default
