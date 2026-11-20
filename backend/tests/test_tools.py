# ==============================================================================
# Quick Test Script for Node 3: Tool Execution & Human Safety Gate
# Run this to verify Step 12 works!
# ==============================================================================

from backend.core.state import AgentState
from backend.core.nodes.tools import ToolExecutionNode, ToolAction

print("--- Testing Node 3: Tool Execution & Human Safety Gate ---")
tools_node = ToolExecutionNode()

# ------------------------------------------------------------------------------
# Test 1: Autonomous Read Tool (search_server_logs)
# ------------------------------------------------------------------------------
state_read = AgentState(incident_report="Checkout service failing with 504")
read_action = ToolAction(
    tool_name="search_server_logs",
    tool_type="read",
    parameters={"keyword": "504"}
)

print("\n1. Testing Autonomous Read Action:")
state_read = tools_node(state_read, pending_action=read_action)
print(f"   Approval Required? {state_read.requires_approval}")
print(f"   Step History:      {state_read.step_history[-1]}")
print(f"   Execution Result:\n   {read_action.execution_result}")

assert state_read.requires_approval is False
assert read_action.execution_result is not None
assert "504 Gateway Timeout" in read_action.execution_result

# ------------------------------------------------------------------------------
# Test 2: Guarded Write Tool -> PAUSE (human_approved is None)
# ------------------------------------------------------------------------------
state_write = AgentState(incident_report="Memory critical outage")
write_action = ToolAction(
    tool_name="execute_remediation_command",
    tool_type="write",
    parameters={"command": "redis-cli config set activedefrag yes"}
)

print("\n2. Testing Guarded Write Action (Expect PAUSE):")
state_write = tools_node(state_write, pending_action=write_action)
print(f"   Approval Required? {state_write.requires_approval}")
print(f"   Step History:      {state_write.step_history[-1]}")

assert state_write.requires_approval is True
assert write_action.execution_result is None, "Tool should NOT execute without approval!"

# ------------------------------------------------------------------------------
# Test 3: Human clicks APPROVED (human_approved = True)
# ------------------------------------------------------------------------------
print("\n3. Testing Human Clicks APPROVE:")
state_write.human_approved = True
state_write = tools_node(state_write, pending_action=write_action)
print(f"   Approval Required? {state_write.requires_approval}")
print(f"   Step History:      {state_write.step_history[-1]}")
print(f"   Execution Result:  {write_action.execution_result}")

assert state_write.requires_approval is False
assert write_action.execution_result is not None
assert "[EXECUTED SUCCESSFULLY]" in write_action.execution_result

# ------------------------------------------------------------------------------
# Test 4: Human clicks REJECTED (human_approved = False)
# ------------------------------------------------------------------------------
print("\n4. Testing Human Clicks REJECT:")
state_reject = AgentState(incident_report="Outage", human_approved=False)
state_reject = tools_node(state_reject, pending_action=write_action)
print(f"   Approval Required? {state_reject.requires_approval}")
print(f"   Step History:      {state_reject.step_history[-1]}")

assert "REJECTED BY HUMAN" in state_reject.step_history[-1]

print("\nSUCCESS: ToolExecutionNode autonomously runs reads, pauses on writes, and enforces human approval!")
