# ==============================================================================
# Step 7: The Hybrid Search Engine (The Smart Librarian)
# File: backend/src/backend/ingestion/hybrid_store.py
#
# FOR BEGINNERS:
# In this file, we combine TWO search methods to get the best of both worlds:
# 1. BM25 (Keyword Search): Finds exact technical words (like "ERR_OOM_504" or "--bigkeys").
# 2. Qdrant (Vector Search): Finds conceptual meaning (like "database running out of memory").
# 3. RRF (Reciprocal Rank Fusion): A math formula that merges both search results.
# ==============================================================================

import os
import re
import logging
from typing import List, Dict, Tuple, Optional

# BM25 is the classic keyword search algorithm (similar to Elasticsearch)
from rank_bm25 import BM25Okapi

# Qdrant is our Vector Database. It can store points in a local folder without Docker!
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

# Import our 'Index Card' blueprint and our Token Budgeter
from backend.ingestion.models import DocumentChunk
from backend.ingestion.tokenizer import prune_chunks_to_budget

logger = logging.getLogger(__name__)


def tokenize_for_keywords(text: str) -> List[str]:
    """
    Helper function for BM25 Keyword Search.
    Extracts individual words, error codes, and technical symbols (like hyphens, underscores, dots).
    Preserves flags like '--bigkeys' and error codes like 'ERR_OOM_COMMAND_NOT_ALLOWED'.
    """
    # Keep words, hyphens, underscores, and dots (standard for CLI flags and error codes)
    raw_tokens = re.findall(r"[a-zA-Z0-9_\.\-]+", text.lower())
    # Strip leading/trailing punctuation from tokens
    clean_tokens = [t.strip("-.") for t in raw_tokens if len(t.strip("-.")) > 1]
    return clean_tokens


class HybridSearchStore:
    """
    The Hybrid Search Librarian:
    Holds all our index cards in two catalogs:
    1. A keyword catalog (BM25)
    2. A vector coordinates catalog (Qdrant)
    """

    def __init__(
        self,
        collection_name: str = "incident_runbooks",
        storage_path: str = "./qdrant_data",
        google_api_key: Optional[str] = None
    ):
        self.collection_name = collection_name
        self.storage_path = storage_path
        self.google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")

        # 1. Initialize Qdrant Client (runs locally in a folder, zero Docker setup needed!)
        os.makedirs(self.storage_path, exist_ok=True)
        self.qdrant = QdrantClient(path=self.storage_path)

        # Standard dimension size for Google's text-embedding-004 model
        self.vector_size = 768

        # 2. Set up Google Gemini Embeddings if an API key is available
        self.embeddings = None
        if self.google_api_key:
            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                self.embeddings = GoogleGenerativeAIEmbeddings(
                    model="models/text-embedding-004",
                    google_api_key=self.google_api_key
                )
            except Exception as e:
                logger.warning(f"Could not load Gemini Embeddings: {e}")

        # 3. In-memory storage for our cards and keyword search index
        self.cards: List[DocumentChunk] = []
        self.card_lookup: Dict[str, DocumentChunk] = {}
        self.bm25_index: Optional[BM25Okapi] = None
        self.tokenized_corpus: List[List[str]] = []

        # Ensure the Qdrant drawer (collection) exists
        self._init_qdrant_collection()

    def _init_qdrant_collection(self) -> None:
        """Creates the collection in Qdrant if it does not already exist."""
        existing_collections = [c.name for c in self.qdrant.get_collections().collections]
        if self.collection_name not in existing_collections:
            self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=self.vector_size,
                    distance=qmodels.Distance.COSINE
                )
            )

    def _get_embedding_vector(self, text: str) -> List[float]:
        """
        Converts text into a list of 768 numbers representing its meaning.
        If no API key is provided, generates a deterministic local vector so offline tests work!
        """
        if self.embeddings:
            try:
                return self.embeddings.embed_query(text)
            except Exception as err:
                logger.warning(f"Gemini API call failed ({err}), falling back to local vector.")

        # Local fallback vector (allows testing without an internet connection or API key)
        import hashlib
        import random
        seed = int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)
        rng = random.Random(seed)
        raw_vector = [rng.uniform(-1.0, 1.0) for _ in range(self.vector_size)]
        # Normalize the vector so its length is 1.0 (Cosine math)
        length = sum(x * x for x in raw_vector) ** 0.5
        return [x / length for x in raw_vector]

    def index_cards(self, cards: List[DocumentChunk]) -> int:
        """
        Takes a list of DocumentChunk cards and indexes them in both:
        1. BM25 (words)
        2. Qdrant (vectors)
        """
        if not cards:
            return 0

        self.cards.extend(cards)
        qdrant_points: List[qmodels.PointStruct] = []
        new_tokenized_docs: List[List[str]] = []

        for card in cards:
            # Store in quick lookup dictionary by ID
            self.card_lookup[card.chunk_id] = card

            # Prepare text for keyword search
            full_text = f"{card.section_title or ''} {card.content}"
            tokens = tokenize_for_keywords(full_text)
            new_tokenized_docs.append(tokens)

            # Compute vector coordinates for semantic search
            vector = self._get_embedding_vector(full_text)

            # Create a Qdrant data point
            point_id = abs(hash(card.chunk_id)) % (2**63 - 1)
            qdrant_points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "chunk_id": card.chunk_id,
                        "source": card.source,
                        "section_title": card.section_title,
                        "token_count": card.token_count,
                        "content": card.content
                    }
                )
            )

        # Upload points to Qdrant
        self.qdrant.upsert(
            collection_name=self.collection_name,
            points=qdrant_points
        )

        # Update BM25 keyword index
        self.tokenized_corpus.extend(new_tokenized_docs)
        self.bm25_index = BM25Okapi(self.tokenized_corpus)

        return len(cards)

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        rrf_k: int = 60,
        max_context_tokens: int = 4000
    ) -> Tuple[List[DocumentChunk], int]:
        """
        The Master Search Function:
        1. Searches BM25 for exact keyword matches.
        2. Searches Qdrant for conceptual vector matches.
        3. Merges ranks using Reciprocal Rank Fusion (RRF).
        4. Trims the final list so it fits inside our token budget!
        
        Returns:
            (best_cards, total_tokens_used)
        """
        if not self.cards:
            return [], 0

        # --- 1. BM25 Keyword Search ---
        bm25_ranks: Dict[str, int] = {}
        if self.bm25_index:
            query_tokens = tokenize_for_keywords(query)
            if query_tokens:
                scores = self.bm25_index.get_scores(query_tokens)
                # Sort indices by score descending
                sorted_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
                for rank, idx in enumerate(sorted_indices[:top_k * 2]):
                    # Only count if the score is greater than 0
                    if scores[idx] > 0:
                        card_id = self.cards[idx].chunk_id
                        bm25_ranks[card_id] = rank + 1  # 1-based rank (1st, 2nd, 3rd)

        # --- 2. Qdrant Dense Vector Search ---
        vector_ranks: Dict[str, int] = {}
        try:
            query_vector = self._get_embedding_vector(query)
            hits = self.qdrant.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k * 2
            ).points
            for rank, hit in enumerate(hits):
                card_id = hit.payload.get("chunk_id")
                if card_id:
                    vector_ranks[card_id] = rank + 1
        except Exception as e:
            logger.warning(f"Vector search warning: {e}")

        # --- 3. Reciprocal Rank Fusion (RRF) ---
        # Formula: Score = 1 / (60 + BM25_Rank) + 1 / (60 + Vector_Rank)
        all_candidate_ids = set(bm25_ranks.keys()).union(set(vector_ranks.keys()))
        rrf_scores: Dict[str, float] = {}

        for cid in all_candidate_ids:
            score = 0.0
            if cid in bm25_ranks:
                score += 1.0 / (rrf_k + bm25_ranks[cid])
            if cid in vector_ranks:
                score += 1.0 / (rrf_k + vector_ranks[cid])
            rrf_scores[cid] = score

        # Sort all candidates by their combined RRF score (highest first)
        sorted_card_ids = sorted(
            rrf_scores.keys(),
            key=lambda cid: rrf_scores[cid],
            reverse=True
        )

        # Retrieve the actual DocumentChunk objects
        ranked_cards = [
            self.card_lookup[cid]
            for cid in sorted_card_ids
            if cid in self.card_lookup
        ][:top_k]

        # If neither search found anything, fallback to top cards
        if not ranked_cards and self.cards:
            ranked_cards = self.cards[:top_k]

        # --- 4. Budget Pruner ---
        # Make sure the top cards fit within our max token budget
        budgeted_cards, tokens_used = prune_chunks_to_budget(
            ranked_cards,
            max_tokens=max_context_tokens
        )

        return budgeted_cards, tokens_used

    def close(self) -> None:
        """Safely close Qdrant storage."""
        try:
            self.qdrant.close()
        except Exception:
            pass
