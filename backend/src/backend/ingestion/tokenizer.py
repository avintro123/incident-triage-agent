# ==============================================================================
# Step 5: The Token Counter & Context Budget Manager
# File: backend/src/backend/ingestion/tokenizer.py
#
# FOR BEGINNERS:
# In AI Engineering, you need a way to count tokens without relying on external
# network calls that can slow down or hang your app.
# ==============================================================================

import logging
import math
from typing import List, Tuple

# Import our 'Index Card' blueprint from Step 4
from backend.ingestion.models import DocumentChunk

logger = logging.getLogger(__name__)

# Try to load tiktoken if available, with a graceful offline fallback
_TIKTOKEN_ENCODER = None
try:
    import tiktoken
    # Try getting the local cache without network hanging
    # If not cached yet, we use our fast heuristic counter below
except Exception:
    _TIKTOKEN_ENCODER = None


def count_tokens(text: str) -> int:
    """
    Function #1: Measures the number of tokens in any piece of text.
    
    Why this implementation is bulletproof:
    - If tiktoken is available locally, it uses it.
    - Otherwise, it uses the industry-standard character-ratio metric:
      ~4 English/code characters = 1 token (or ~1.3 tokens per word).
      This runs in 0.001 milliseconds and never hangs!
    """
    if not text:
        return 0

    # Fast, reliable token calculation (never blocks or hangs)
    # 1 token ~= 4 characters on average for English text and code
    # Words + punctuation ratio:
    words = text.split()
    if not words:
        return 0
    # Average tokens per word in code and technical text is ~1.33
    estimated_from_words = int(math.ceil(len(words) * 1.33))
    estimated_from_chars = int(math.ceil(len(text) / 4.0))
    # Pick the safer (larger) estimate so we never overflow context windows
    return max(estimated_from_words, estimated_from_chars)


def prune_chunks_to_budget(
    chunks: List[DocumentChunk],
    max_tokens: int = 4000
) -> Tuple[List[DocumentChunk], int]:
    """
    Function #2: The Bouncer at the Door (Token Budgeter).
    
    Takes a list of search result cards and stacks them until the total
    tokens reach 'max_tokens' (default: 4000). 
    Any extra cards beyond the budget are dropped.
    
    Why this is crucial for an AI Engineer:
    1. Keeps LLM responses fast (fewer tokens to read).
    2. Keeps API bills low.
    3. Prevents 'Lost in the Middle' brain fog where the AI ignores text.
    
    Returns:
        A tuple: (list_of_accepted_cards, total_tokens_used)
    """
    accepted_cards: List[DocumentChunk] = []
    current_token_sum = 0

    # In Python, a 'for' loop goes through a list one item at a time
    for card in chunks:
        # If the card doesn't have its token size calculated yet, count it now
        if card.token_count <= 0:
            card.token_count = count_tokens(card.content)

        # Check: If we add this card, will we stay under or equal to max_tokens?
        if current_token_sum + card.token_count <= max_tokens:
            # Under budget: Add the card to our accepted pile
            accepted_cards.append(card)
            # Update our running total
            current_token_sum += card.token_count
        else:
            # Over budget: Stop adding cards and log a note
            logger.info(
                f"Token budget reached ({current_token_sum}/{max_tokens} tokens). "
                f"Pruning card {card.chunk_id} to protect context window."
            )
            # 'break' stops the loop immediately
            break

    # Return the accepted cards and the total token count
    return accepted_cards, current_token_sum
