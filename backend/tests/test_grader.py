# ==============================================================================
# Quick Test Script for Node 2: Retrieval Grader & Query Rewriter
# Run this to verify Step 11 works!
# ==============================================================================

from backend.core.state import AgentState
from backend.core.nodes.grader import RetrievalGraderNode
from backend.ingestion.models import DocumentChunk

print("--- Testing Node 2: Retrieval Grader & Query Rewriter ---")
grader = RetrievalGraderNode(max_retries=3)

# ------------------------------------------------------------------------------
# Test 1: High Quality Evidence -> Expect PASS
# ------------------------------------------------------------------------------
state_good = AgentState(
    incident_report="Redis memory exhausted with ERR_OOM_COMMAND_NOT_ALLOWED"
)
state_good.retrieved_docs.append(
    DocumentChunk(
        chunk_id="redis_runbook_sec3",
        content="Execute 'redis-cli config set activedefrag yes' to resolve ERR_OOM_COMMAND_NOT_ALLOWED.",
        source="runbook_redis.md",
        doc_type="markdown",
        section_title="3. Mitigation and Recovery Steps"
    )
)

print("\n1. Testing with Relevant Evidence:")
state_good = grader(state_good)
print(f"   Verdict:      {state_good.grader_verdict}")
print(f"   Step History: {state_good.step_history[-1]}")
assert state_good.grader_verdict == "pass", "Expected good evidence to pass!"

# ------------------------------------------------------------------------------
# Test 2: Irrelevant Evidence -> Expect REJECT & REWRITE LOOP
# ------------------------------------------------------------------------------
state_bad = AgentState(
    incident_report="Redis memory exhausted with ERR_OOM_COMMAND_NOT_ALLOWED"
)
state_bad.retrieved_docs.append(
    DocumentChunk(
        chunk_id="office_wifi",
        content="The Wi-Fi router in the lobby operates on 5GHz. Password is on the whiteboard.",
        source="office_it.md",
        doc_type="markdown",
        section_title="Lobby Wi-Fi"
    )
)

print("\n2. Testing with Irrelevant Evidence (Expect Loop Back):")
state_bad = grader(state_bad)
print(f"   Verdict:         {state_bad.grader_verdict}")
print(f"   Retry Count:     {state_bad.search_retry_count}/3")
print(f"   Rewritten Query: {state_bad.sub_queries}")
print(f"   Step History:    {state_bad.step_history[-1]}")

assert state_bad.grader_verdict == "rewrite_query"
assert state_bad.search_retry_count == 1
assert len(state_bad.sub_queries) == 1

# ------------------------------------------------------------------------------
# Test 3: Loop Guard Protection -> Max Retries Reached
# ------------------------------------------------------------------------------
print("\n3. Testing Loop Guard Protection (Max Retries = 3):")
state_bad.search_retry_count = 3  # Simulate having already tried 3 times
state_bad = grader(state_bad)
print(f"   Verdict:      {state_bad.grader_verdict}")
print(f"   Step History: {state_bad.step_history[-1]}")

assert state_bad.grader_verdict == "pass"

print("\nSUCCESS: RetrievalGraderNode correctly passes gold evidence, loops back on bad data, and guards against infinite loops!")
