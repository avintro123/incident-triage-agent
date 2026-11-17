# ==============================================================================
# Quick Test Script for Node 1: Query Router & Sub-query Planner
# Run this to verify Step 10 works!
# ==============================================================================

from backend.core.state import AgentState
from backend.core.nodes.router import QueryRouterNode

print("--- Testing Node 1: Query Router & Planner ---")
router_node = QueryRouterNode()

# Case A: Real-world messy incident report
state_a = AgentState(
    incident_report="API gateway throwing 504 on /checkout. REDIS_MEM_CRITICAL alert triggered. Need immediate triage."
)

print(f"\n1. Incoming Alert: \"{state_a.incident_report}\"")
updated_state_a = router_node(state_a)

print("\nPlanner Output:")
print(f"   Sub-queries Generated: {updated_state_a.sub_queries}")
print(f"   Step History:          {updated_state_a.step_history[-1]}")

assert len(updated_state_a.sub_queries) >= 1
assert any("REDIS_MEM_CRITICAL" in q for q in updated_state_a.sub_queries)

# Case B: Vague report that needs human clarification
state_b = AgentState(incident_report="help")
print(f"\n2. Vague Alert: \"{state_b.incident_report}\"")
updated_state_b = router_node(state_b)
print(f"   Step History: {updated_state_b.step_history[-1]}")

assert "ask_clarification" in updated_state_b.step_history[-1]

print("\nSUCCESS: QueryRouterNode cleanly parses messy incident reports into targeted search queries!")
