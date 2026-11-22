# ==============================================================================
# Quick Test Script for Complete LangGraph State Machine
# Run this to verify Step 14 works end-to-end!
# ==============================================================================

import shutil
from pathlib import Path
from backend.ingestion.parser import StructureAwareParser
from backend.ingestion.hybrid_store import HybridSearchStore
from backend.core.graph import IncidentTriageGraph

print("--- Testing Full LangGraph Incident Triage Graph ---")

test_dir = "./test_graph_qdrant"
if Path(test_dir).exists():
    shutil.rmtree(test_dir, ignore_errors=True)

# 1. Parse and index our sample Redis runbook
parser = StructureAwareParser()
cards = parser.parse_file("data/sample_docs/runbook_redis_cluster.md")
store = HybridSearchStore(collection_name="test_graph_collection", storage_path=test_dir)
store.index_cards(cards)
print(f"1. Prepared knowledge base with {len(cards)} indexed cards.")

# 2. Build the LangGraph State Machine
triage_agent = IncidentTriageGraph(hybrid_store=store)
print("2. LangGraph state machine compiled successfully.")

# 3. Simulate an emergency production alert
alert = "API gateway throwing 504 on /checkout. REDIS_MEM_CRITICAL alert triggered. Need immediate triage."
print(f"\n3. Submitting Incoming Production Alert:\n   \"{alert}\"\n")

# 4. Invoke the Graph!
final_state = triage_agent.invoke(alert)

# 5. Inspect the Results
print("=" * 70)
print("INVESTIGATION COMPLETE! Results in AgentState:")
print("=" * 70)

print("\n--- A. STEP HISTORY (Audit Trail) ---")
for step_num, step in enumerate(final_state.step_history, 1):
    print(f"  Step {step_num}: {step}")

print("\n--- B. SUB-QUERIES PLANNED ---")
print(f"  {final_state.sub_queries}")

print("\n--- C. EVIDENCE CARDS RETRIEVED ---")
for doc in final_state.retrieved_docs:
    print(f"  - {doc.citation_label()}")

print("\n--- D. FINAL VERIFIED OUTPUT ---")
print(f"  {final_state.final_output}")

print("\n--- E. CITATIONS ATTACHED ---")
print(f"  {final_state.citations}")

# Assertions
assert len(final_state.step_history) >= 4, "Expected at least 4 workflow steps!"
assert len(final_state.retrieved_docs) > 0, "Expected searcher to retrieve evidence!"
assert len(final_state.citations) > 0, "Expected auditor to attach citations!"
assert "runbook_redis_cluster.md" in final_state.citations[0]

# Clean up
store.close()
shutil.rmtree(test_dir, ignore_errors=True)

print("\nSUCCESS: Complete LangGraph State Machine ran end-to-end flawlessly!")
