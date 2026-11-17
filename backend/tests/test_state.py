

# ==============================================================================
# Quick Test Script for AgentState (The Case File)
# Run this to verify Step 9 works!
# ==============================================================================

from backend.core.state import AgentState
from backend.ingestion.models import DocumentChunk

print("--- Testing AgentState (The Case File) ---")

# 1. Create a new case file when an incident occurs
state = AgentState(
    incident_report="Checkout service failing with 504 Gateway Timeout. Redis memory critical."
)
print(f"1. New Case Opened: \"{state.incident_report}\"")

# 2. Detective 1 (Planner) adds sub-queries and logs step
state.sub_queries = ["Redis memory exhaustion", "504 Gateway Timeout checkout"]
state.step_history.append("Planner: Generated 2 sub-queries")
print(f"2. Planner Added Queries: {state.sub_queries}")

# 3. Searcher adds retrieved evidence cards
state.retrieved_docs.append(
    DocumentChunk(
        chunk_id="redis_s3",
        content="Run active defragmentation to clear memory pressure.",
        source="runbook_redis_cluster.md",
        doc_type="markdown",
        section_title="Mitigation and Recovery Steps"
    )
)
state.step_history.append("Searcher: Retrieved 1 gold card")

# 4. Grader passes the evidence
state.grader_verdict = "pass"
state.step_history.append("Grader: Evidence passed relevance check")

# 5. Doctor generates draft diagnosis and flags human approval
state.draft_diagnosis = "Redis memory pressure caused the 504 outage. Recommended fix: active defragmentation."
state.citations = [state.retrieved_docs[0].citation_label()]
state.requires_approval = True
state.step_history.append("Diagnostician: Drafted fix, waiting for human approval")

print("\n3. Current Case File Summary:")
print(f"   Draft:     {state.draft_diagnosis}")
print(f"   Citations: {state.citations}")
print(f"   Approval Required? {state.requires_approval}")
print(f"   Steps:     {state.step_history}")

assert len(state.sub_queries) == 2
assert state.grader_verdict == "pass"
assert state.requires_approval is True

print("\nSUCCESS: AgentState cleanly tracks the entire investigation workflow!")
