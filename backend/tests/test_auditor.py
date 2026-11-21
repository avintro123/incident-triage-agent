# ==============================================================================
# Quick Test Script for Node 4: Citation & Hallucination Auditor
# Run this to verify Step 13 works!
# ==============================================================================

from backend.core.state import AgentState
from backend.core.nodes.auditor import CitationAuditorNode
from backend.ingestion.models import DocumentChunk

print("--- Testing Node 4: Citation & Hallucination Auditor ---")
auditor = CitationAuditorNode()

# Ground Truth Card
real_card = DocumentChunk(
    chunk_id="redis_s3",
    content="Execute `redis-cli config set activedefrag yes` to recover from memory pressure.",
    source="runbook_redis_cluster.md",
    doc_type="markdown",
    section_title="3. Mitigation and Recovery Steps"
)

# ------------------------------------------------------------------------------
# Test 1: Faithful Diagnosis (Supported by Ground Truth)
# ------------------------------------------------------------------------------
state_good = AgentState(
    incident_report="Redis memory critical",
    draft_diagnosis="The cluster is running out of memory. Execute `redis-cli config set activedefrag yes` to mitigate.",
    retrieved_docs=[real_card]
)

print("\n1. Testing Faithful Diagnosis:")
state_good = auditor(state_good)
print(f"   Final Output:\n   {state_good.final_output}")
print(f"   Citations Attached: {state_good.citations}")
print(f"   Step History:       {state_good.step_history[-1]}")

assert len(state_good.citations) == 1
assert "[runbook_redis_cluster.md" in state_good.citations[0]
assert "UNVERIFIED" not in state_good.final_output

# ------------------------------------------------------------------------------
# Test 2: Hallucinated Dangerous Command (NOT in Ground Truth)
# ------------------------------------------------------------------------------
state_bad = AgentState(
    incident_report="Redis memory critical",
    draft_diagnosis="Execute `redis-cli flushall` to wipe the cache immediately. Also run `redis-cli config set activedefrag yes`.",
    retrieved_docs=[real_card]
)

print("\n2. Testing Hallucination Detection & Stripping:")
state_bad = auditor(state_bad)
print(f"   Final Output:\n   {state_bad.final_output}")
print(f"   Step History: {state_bad.step_history[-1]}")

assert "UNVERIFIED CLAIM REMOVED" in state_bad.final_output
assert "flushall" in state_bad.step_history[-1]

print("\nSUCCESS: CitationAuditorNode attaches verified citations and strips fake hallucinated commands!")
