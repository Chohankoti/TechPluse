from __future__ import annotations
import logging
from typing import Any
import numpy as np
from jsonc_parser.parser import JsoncParser
from sentence_transformers import SentenceTransformer, util

logger = logging.getLogger(__name__)

class RelevanceChecker:
    """
    Semantic relevance evaluator using SentenceTransformer models.
    Pre-vectorizes user constraints and performs cosine similarity matching
    against blog titles and full web content.
    """
    def __init__(
        self,
        constraints_path: str,
        model_name: str = "all-MiniLM-L6-v2",
        title_threshold: float = 0.35,
        content_threshold: float = 0.55,
        fallback_threshold: float = 0.60
    ) -> None:
        self.constraints_path = constraints_path
        self.model_name = model_name
        self.title_threshold = title_threshold
        self.content_threshold = content_threshold
        self.fallback_threshold = fallback_threshold

        logger.info("Initializing SentenceTransformer with model: %s", self.model_name)
        self.model = SentenceTransformer(self.model_name)
        
        # Precompute constraint vectors
        self.categories, self.constraint_phrases, self.constraint_embeddings = self._precompute_constraint_embeddings()

    def _precompute_constraint_embeddings(self) -> tuple[list[str], list[str], Any]:
        """Loads constraints JSONC and pre-encodes all constraint phrases."""
        try:
            constraints_dict = JsoncParser().parse_file(self.constraints_path)
        except Exception as e:
            logger.error("Failed to load user constraints from %s: %s", self.constraints_path, e)
            constraints_dict = {}

        categories: list[str] = []
        phrases: list[str] = []

        if isinstance(constraints_dict, dict):
            for category, phrase_list in constraints_dict.items():
                if isinstance(phrase_list, list):
                    for phrase in phrase_list:
                        categories.append(str(category))
                        phrases.append(str(phrase))

        if not phrases:
            logger.warning("No constraint phrases found in %s", self.constraints_path)
            embeddings = np.array([])
        else:
            logger.info("Pre-vectorizing %d constraint phrases...", len(phrases))
            embeddings = self.model.encode(phrases, convert_to_tensor=True, normalize_embeddings=True)

        return categories, phrases, embeddings

    def check_title_relevance(self, title: str) -> tuple[bool, float, dict[str, Any] | None]:
        """Evaluates whether title passes the title relevance threshold."""
        if not title or len(self.constraint_phrases) == 0:
            return False, 0.0, None

        title_embedding = self.model.encode(title, convert_to_tensor=True, normalize_embeddings=True)
        cosine_scores = util.cos_sim(title_embedding, self.constraint_embeddings)[0]
        
        max_idx = int(np.argmax(cosine_scores.cpu().numpy()))
        max_score = float(cosine_scores[max_idx])

        match_info = {
            "category": self.categories[max_idx],
            "constraint": self.constraint_phrases[max_idx],
            "score": round(max_score, 4)
        }

        is_relevant = max_score >= self.title_threshold
        return is_relevant, max_score, match_info

    def check_content_relevance(self, text: str) -> tuple[bool, float, dict[str, Any] | None]:
        """Evaluates chunked article body text against constraint vectors."""
        if not text or len(self.constraint_phrases) == 0:
            return False, 0.0, None

        chunks = self._chunk_text(text)
        if not chunks:
            return False, 0.0, None

        chunk_embeddings = self.model.encode(chunks, convert_to_tensor=True, normalize_embeddings=True)
        cosine_matrix = util.cos_sim(chunk_embeddings, self.constraint_embeddings)

        matrix_np = cosine_matrix.cpu().numpy()
        flat_idx = int(np.argmax(matrix_np))
        chunk_idx, constraint_idx = np.unravel_index(flat_idx, matrix_np.shape)
        max_score = float(matrix_np[chunk_idx, constraint_idx])

        match_info = {
            "category": self.categories[constraint_idx],
            "constraint": self.constraint_phrases[constraint_idx],
            "score": round(max_score, 4),
            "matched_snippet": chunks[chunk_idx][:120] + "..." if len(chunks[chunk_idx]) > 120 else chunks[chunk_idx]
        }

        is_relevant = max_score >= self.content_threshold
        return is_relevant, max_score, match_info

    def _chunk_text(self, text: str, chunk_size: int = 250, overlap: int = 50) -> list[str]:
        """Splits markdown/text into sliding window paragraph chunks."""
        paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 30]
        if not paragraphs:
            words = text.split()
            if not words:
                return []
            chunks = []
            for i in range(0, len(words), chunk_size - overlap):
                chunks.append(" ".join(words[i:i + chunk_size]))
            return chunks
        
        merged_chunks = []
        current_chunk = []
        current_len = 0

        for p in paragraphs:
            word_count = len(p.split())
            if current_len + word_count <= chunk_size:
                current_chunk.append(p)
                current_len += word_count
            else:
                if current_chunk:
                    merged_chunks.append("\n".join(current_chunk))
                current_chunk = [p]
                current_len = word_count
        
        if current_chunk:
            merged_chunks.append("\n".join(current_chunk))

        return merged_chunks

    def generate_reason_description(self, match_info: dict[str, Any], is_from_content: bool = False) -> str:
        """Formats an explanatory 'why' string for content state persistence."""
        category = match_info.get("category", "General")
        constraint = match_info.get("constraint", "") 
        score = match_info.get("score", 0.0)

        if is_from_content:
            return f"Matched with content score: {score} '{category}': {constraint}"
        else:
            return f"Matched with title score: {score} '{category}': {constraint}"
        
