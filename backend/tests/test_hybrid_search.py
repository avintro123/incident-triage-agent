# ==============================================================================
# Quick Test Script for Hybrid Search Engine (BM25 + Qdrant + RRF)
# Run this to verify Step 7 works!
# ==============================================================================

import shutil
from pathlib import Path
from backend.ingestion.parser import StructureAwareParser
from backend.ingestion.hybrid_store import HybridSearchStore

print("--- Testing Hybrid Search Store ---")

test_storage = "./test_qdrant_data"
if Path(test_storage).exists():
    shutil.rmtree(test_storage, ignore_errors=True)

# 1. Parse sample runbook into smart cards
parser = StructureAwareParser()
runbook_path = "data/sample_docs/runbook_redis_cluster.md"
cards = parser.parse_file(runbook_path)
print(f"1. Sliced '{runbook_path}' into {len(cards)} cards.")

# 2. Index cards into our Hybrid Search Librarian
store = HybridSearchStore(collection_name="test_incidents", storage_path=test_storage)
indexed_count = store.index_cards(cards)
print(f"2. Indexed {indexed_count} cards into Qdrant & BM25.")

# 3. Test exact keyword search (BM25 superpower)
exact_query = "ERR_OOM_COMMAND_NOT_ALLOWED"
print(f"\n3. Testing Exact Error Code Search: '{exact_query}'")
results, tokens_used = store.hybrid_search(exact_query, top_k=3)

for i, card in enumerate(results, 1):
    print(f"   Rank #{i}: {card.citation_label()}")
    print(f"   ID:       {card.chunk_id} ({card.token_count} tokens)")
    print(f"   Snippet:  {card.content[:90].replace(chr(10), ' ')}...\n")

# Verify we found the card with the error
assert any("ERR_OOM_COMMAND_NOT_ALLOWED" in c.content for c in results), "Failed to find error code!"

# 4. Test diagnostics command search
cmd_query = "bigkeys"
print(f"4. Testing Exact Command Search: '{cmd_query}'")
results, tokens_used = store.hybrid_search(cmd_query, top_k=3)

for i, card in enumerate(results, 1):
    print(f"   Rank #{i}: {card.citation_label()}")
    print(f"   Snippet:  {card.content[:90].replace(chr(10), ' ')}...\n")

assert any("bigkeys" in c.content for c in results), "Failed to find command!"

# 5. Clean up
store.close()
shutil.rmtree(test_storage, ignore_errors=True)

print("SUCCESS: Hybrid Search (BM25 + Qdrant + RRF) works flawlessly!")
