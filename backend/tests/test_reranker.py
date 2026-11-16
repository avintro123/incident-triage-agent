# ==============================================================================
# Quick Test Script for Document Reranker
# Run this to verify Step 8 works!
# ==============================================================================

from backend.ingestion.models import DocumentChunk
from backend.ingestion.reranker import DocumentReranker

print("--- Testing Document Reranker ---")
reranker = DocumentReranker(min_relevance_threshold=0.30)

# Simulate 3 candidate cards returned from a broad search
card_good = DocumentChunk(
    chunk_id="card_recovery",
    content="Execute redis-cli config set activedefrag yes to mitigate ERR_OOM_COMMAND_NOT_ALLOWED.",
    source="runbook_redis.md",
    doc_type="markdown",
    section_title="Mitigation and Recovery Steps"
)

card_partial = DocumentChunk(
    chunk_id="card_symptoms",
    content="Users experience 504 Gateway Timeout during peak traffic spikes.",
    source="runbook_redis.md",
    doc_type="markdown",
    section_title="Overview and Symptoms"
)

card_irrelevant = DocumentChunk(
    chunk_id="card_unrelated",
    content="How to configure Wi-Fi printer in conference room 3B.",
    source="office_setup.md",
    doc_type="markdown",
    section_title="Office IT"
)

candidates = [card_good, card_partial, card_irrelevant]
query = "How to fix ERR_OOM_COMMAND_NOT_ALLOWED using redis-cli"

print(f"User Query: '{query}'")
print(f"Candidates before reranking: {len(candidates)} cards\n")

# Run the reranker
reranked = reranker.rerank(query, candidates, top_n=2)

print(f"After Reranking (Top {len(reranked)} kept):")
for rank, (card, score) in enumerate(reranked, 1):
    print(f"  Rank #{rank}: {card.chunk_id}")
    print(f"    Relevance Score: {score * 100:.1f}%")
    print(f"    Section:         {card.section_title}")
    print(f"    Snippet:         \"{card.content}\"\n")

# Assertions: Verify quality
assert reranked[0][0].chunk_id == "card_recovery", "Best card was not ranked #1!"
assert not any(c.chunk_id == "card_irrelevant" for c, _ in reranked), "Irrelevant card was not filtered out!"

print("SUCCESS: Reranker correctly scored the best card #1 and stripped irrelevant noise!")
