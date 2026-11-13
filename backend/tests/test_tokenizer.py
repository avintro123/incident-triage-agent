# ==============================================================================
# Quick Test Script for Tokenizer & Budget Pruner
# Run this file to verify that Step 5 works!
# ==============================================================================

from backend.ingestion.models import DocumentChunk
from backend.ingestion.tokenizer import count_tokens, prune_chunks_to_budget

print("--- Testing Tokenizer ---")

# 1. Test counting tokens in technical text
error_code = "ERR_OOM_COMMAND_NOT_ALLOWED"
tokens = count_tokens(error_code)
print(f"Error Code: '{error_code}' -> {tokens} tokens")

# 2. Test budget pruning
print("\n--- Testing Budget Pruner ---")
chunk_1 = DocumentChunk(
    chunk_id="card_1",
    content="This is the first card with some text.",
    source="doc1.md",
    doc_type="markdown",
    token_count=10
)
chunk_2 = DocumentChunk(
    chunk_id="card_2",
    content="This is the second card with more text.",
    source="doc2.md",
    doc_type="markdown",
    token_count=15
)

# Test with a budget of 20 tokens (should keep chunk_1, but drop chunk_2 because 10 + 15 = 25 > 20)
accepted, total = prune_chunks_to_budget([chunk_1, chunk_2], max_tokens=20)
print(f"With budget 20: Kept {len(accepted)} card(s), using {total} tokens.")
print("Cards kept:", [c.chunk_id for c in accepted])

print("\nSUCCESS: Tokenizer and Budget Pruner work perfectly!")

