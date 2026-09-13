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

    def check_content_relevance(self, text: str, title: str = "") -> tuple[bool, float, dict[str, Any] | None]:
        """Evaluates chunked article body text against constraint vectors."""
        if not text or len(self.constraint_phrases) == 0:
            return False, 0.0, None

        chunks = self._chunk_text(text, chunk_size=130, overlap=30)
        if not chunks:
            return False, 0.0, None

        if title:
            chunks = [f"[Title: {title}] {chunk}" for chunk in chunks]

        chunk_embeddings = self.model.encode(chunks, convert_to_tensor=True, normalize_embeddings=True)
        cosine_matrix = util.cos_sim(chunk_embeddings, self.constraint_embeddings)

        matrix_np = cosine_matrix.cpu().numpy()
        flat_idx = int(np.argmax(matrix_np))
        chunk_idx, constraint_idx = np.unravel_index(flat_idx, matrix_np.shape)
        max_score = float(matrix_np[chunk_idx, constraint_idx])

        matching_chunks_mask = matrix_np.max(axis=1) >= 0.38
        multi_match_count = int(np.sum(matching_chunks_mask))

        final_score = max_score
        if multi_match_count >= 2:
            final_score = min(1.0, max_score + 0.03)

        # Extract raw matched chunk without [Title: ...] prefix
        matched_chunk_raw = chunks[chunk_idx]
        if title and matched_chunk_raw.startswith(f"[Title: {title}] "):
            matched_chunk_raw = matched_chunk_raw[len(f"[Title: {title}] "):]

        match_info = {
            "category": self.categories[constraint_idx],
            "constraint": self.constraint_phrases[constraint_idx],
            "score": round(final_score, 4),
            "multi_match_count": multi_match_count,
            "matched_snippet": matched_chunk_raw[:140] + "..." if len(matched_chunk_raw) > 140 else matched_chunk_raw
        }

        is_relevant = final_score >= self.content_threshold
        return is_relevant, final_score, match_info

    def _chunk_text(self, text: str, chunk_size: int = 130, overlap: int = 30) -> list[str]:
        """
        Splits text/markdown into token-optimized sliding window chunks (120-140 words max).
        Preserves Markdown headings, short bullet points, and handles empty spacing cleanly.
        """
        # Filter out empty spacing lines without dropping short headings
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return []

        chunks = []
        current_chunk_words: list[str] = []
        
        for line in lines:
            line_words = line.split()
            
            # If a single paragraph/line exceeds chunk size, split it with sliding window
            if len(line_words) > chunk_size:
                if current_chunk_words:
                    chunks.append(" ".join(current_chunk_words))
                    current_chunk_words = []
                
                step = max(1, chunk_size - overlap)
                for i in range(0, len(line_words), step):
                    sub_words = line_words[i:i + chunk_size]
                    chunks.append(" ".join(sub_words))
                continue

            # Check if adding current line exceeds target chunk word count
            if len(current_chunk_words) + len(line_words) > chunk_size:
                if current_chunk_words:
                    chunks.append(" ".join(current_chunk_words))
                    # Retain last 'overlap' words for sliding window continuity
                    current_chunk_words = current_chunk_words[-overlap:] if overlap < len(current_chunk_words) else current_chunk_words
            
            current_chunk_words.extend(line_words)

        if current_chunk_words:
            chunks.append(" ".join(current_chunk_words))

        return chunks

    def generate_reason_description(self, match_info: dict[str, Any], is_from_content: bool = False) -> str:
        """Formats an explanatory 'why' string for content state persistence."""
        category = match_info.get("category", "General")
        constraint = match_info.get("constraint", "")
        score = match_info.get("score", 0.0)
        snippet = match_info.get("matched_snippet", "")

        if is_from_content and snippet:
            return f"[{category}] {constraint}: \"{snippet}\""
        elif is_from_content:
            return f"[{category}] {constraint}"
        else:
            return f"[{category}] {constraint}"
        
