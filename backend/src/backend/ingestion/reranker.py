# ==============================================================================
# Step 8: The Reranker (The Precision Filter)
# File: backend/src/backend/ingestion/reranker.py
#
# FOR BEGINNERS:
# Why do we need a Reranker?
# Hybrid Search (BM25 + Qdrant) is fast, but it is an approximation. It grabs
# the top 10-15 candidate cards.
#
# The Reranker sits down with each of those 10-15 cards, reads it side-by-side
# with the user's question, and gives each card an exact grade from 0.0 to 1.0.
# Only the true top 3 cards with passing grades are sent to Gemini!
# ==============================================================================

import os
import re
import logging
from typing import List, Tuple, Optional

# Import our 'Index Card' blueprint
from backend.ingestion.models import DocumentChunk

logger = logging.getLogger(__name__)


class   DocumentReranker:
    """
    The Precision Filter:
    Scores candidate cards directly against the user query, sorting them from
    highest relevance to lowest, and filtering out low-scoring noise.
    """

    def __init__(
        self,
        google_api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        min_relevance_threshold: float = 0.25
    ):
        self.google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name
        # Any card scoring below 0.25 (25%) is considered irrelevant noise and dropped
        self.min_relevance_threshold = min_relevance_threshold

    def rerank(
        self,
        query: str,
        candidates: List[DocumentChunk],
        top_n: int = 3
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Takes candidate cards from Hybrid Search and re-scores each one
        against the exact query.
        
        Returns:
            A list of tuples: [(DocumentChunk, score), ...] sorted highest first.
        """
        if not candidates:
            return []

        # If we only have 1 or 2 candidates, no need to over-filter
        if len(candidates) <= top_n:
            scored = [(c, self._score_card(query, c)) for c in candidates]
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored

        # Score every candidate card
        scored_cards: List[Tuple[DocumentChunk, float]] = []
        for card in candidates:
            score = self._score_card(query, card)
            if score >= self.min_relevance_threshold:
                scored_cards.append((card, score))
            else:
                logger.info(f"Reranker dropped low-relevance card: {card.chunk_id} (Score: {score:.2f})")

        # Sort descending by score (best match first)
        scored_cards.sort(key=lambda x: x[1], reverse=True)

        # Return only the top_n (default: 3)
        return scored_cards[:top_n]

    def _score_card(self, query: str, card: DocumentChunk) -> float:
        """
        Calculates a relevance score between 0.0 (irrelevant) and 1.0 (exact match).
        
        Evaluates 3 key criteria:
        1. Exact error code / identifier matches (Huge bonus)
        2. Keyword term coverage between query and content
        3. Header / section title alignment
        """
        query_lower = query.lower()
        content_lower = card.content.lower()
        section_lower = (card.section_title or "").lower()

        # 1. Check for exact code tokens (e.g. ERR_OOM_504, 504, redis-cli)
        query_codes = re.findall(r"[a-z0-9_\.\-]+", query_lower)
        if not query_codes:
            return 0.5  # Neutral fallback

        matched_codes = 0
        for code in query_codes:
            # Skip tiny generic words like 'is', 'a', 'in', 'the'
            if len(code) <= 2:
                continue
            if code in content_lower or code in section_lower:
                matched_codes += 1

        # Calculate word overlap ratio
        meaningful_codes = [c for c in query_codes if len(c) > 2]
        if not meaningful_codes:
            overlap_ratio = 0.5
        else:
            overlap_ratio = matched_codes / len(meaningful_codes)

        # Bonus points if the section header explicitly mentions the topic
        header_bonus = 0.0
        if card.section_title and any(c in section_lower for c in meaningful_codes):
            header_bonus = 0.15

        # Final score capped between 0.0 and 1.0
        final_score = min(1.0, (overlap_ratio * 0.85) + header_bonus)
        return round(final_score, 3)
