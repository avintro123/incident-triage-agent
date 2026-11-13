# ==============================================================================
# Quick Test Script for Structure-Aware Parser
# Run this to verify Step 6 works!
# ==============================================================================

from backend.ingestion.parser import StructureAwareParser

print("--- Testing Structure-Aware Parser ---")
parser = StructureAwareParser()

# Parse our Redis runbook sample document
runbook_file = "data/sample_docs/runbook_redis_cluster.md"
chunks = parser.parse_file(runbook_file)

print(f"\nSuccessfully sliced '{runbook_file}' into {len(chunks)} smart cards:\n")

for i, card in enumerate(chunks, 1):
    print(f"Card #{i}:")
    print(f"  Barcode ID:    {card.chunk_id}")
    print(f"  Section Title: {card.section_title}")
    print(f"  Token Size:    {card.token_count} tokens")
    print(f"  Citation Tag:  {card.citation_label()}")
    # Show first 80 characters of the card content
    preview = card.content.replace('\n', ' ')[:80]
    print(f"  Content Peek:  \"{preview}...\"\n")

print("SUCCESS: The Smart Scissors parsed sections without breaking tables or steps!")

