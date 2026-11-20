# ==============================================================================
# Step 12: Node 3 — Tool Execution & Human-in-the-Loop Safety Gate
# File: backend/src/backend/core/nodes/tools.py
#
# FOR BEGINNERS:
# Why do we need safety gates?
# Giving an autonomous AI the ability to run commands or modify databases
# without supervision can cause catastrophic outages.
#
# This node divides actions into two categories:
# 1. READ TOOLS (Autonomous): Searching logs, checking metrics (100% safe).
# 2. WRITE TOOLS (Guarded): Proposing terminal commands, creating Jira tickets.
#    When a WRITE tool is selected, the agent pauses execution and waits for
#    the engineer to click "Approve" in the UI!
# ==============================================================================

import os
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

# Import our Case File blueprint from Step 9
from backend.core.state import AgentState


class ToolAction(BaseModel):
    """
    Represents an action the agent wants to take.
    """
    tool_name: str = Field(description="Name of the tool: 'search_server_logs', 'draft_jira_ticket', 'propose_command'")
    tool_type: str = Field(description="'read' (autonomous) or 'write' (requires approval)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the tool")
    execution_result: Optional[str] = Field(default=None, description="Output generated after tool execution")


# --- TOOL 1: Read Tool (Autonomous) ---
def search_server_logs(keyword: str, max_lines: int = 5) -> str:
    """
    Searches the server logs for matching timestamps and error traces.
    Autonomous: Safe to run without human intervention.
    """
    log_file = Path("data/mock_logs/incident_oom_crash.log")
    if not log_file.exists():
        return f"Log file not found: {log_file}"

    lines = log_file.read_text(encoding="utf-8").splitlines()
    matches = [line for line in lines if keyword.lower() in line.lower() and not line.strip().startswith("#")]
    
    if not matches:
        return f"No log entries found matching keyword: '{keyword}'"
    
    return "\n".join(matches[:max_lines])


# --- TOOL 2: Write Tool (Guarded) ---
def draft_jira_ticket(title: str, component: str, priority: str, description: str) -> str:
    """
    Drafts an official Jira ticket for post-incident review.
    Guarded: Modifies external ticketing systems.
    """
    return (
        f"[JIRA TICKET DRAFTED]\n"
        f"Key: INC-{abs(hash(title)) % 9000 + 1000}\n"
        f"Component: {component} | Priority: {priority}\n"
        f"Title: {title}\n"
        f"Summary: {description}"
    )


# --- TOOL 3: Write Tool (Guarded) ---
def execute_remediation_command(command: str) -> str:
    """
    Executes an emergency mitigation command on the cluster.
    Guarded: Highly sensitive terminal command.
    """
    return f"[EXECUTED SUCCESSFULLY]: `{command}` -> Cluster state modified."


class ToolExecutionNode:
    """
    Node 3 in the LangGraph State Machine:
    Manages tool execution and enforces the Human-in-the-Loop approval gate.
    """

    def __call__(self, state: AgentState, pending_action: Optional[ToolAction] = None) -> AgentState:
        """
        Executes Node 3:
        Checks if an action is safe or requires human approval.
        """
        if not pending_action:
            # If no specific action is queued, check if we need to inspect logs
            if "search_logs" in state.step_history[-1] or any("504" in q for q in state.sub_queries):
                pending_action = ToolAction(
                    tool_name="search_server_logs",
                    tool_type="read",
                    parameters={"keyword": "504"}
                )
            else:
                return state

        # Case A: READ TOOL (Autonomous)
        if pending_action.tool_type == "read":
            result = search_server_logs(**pending_action.parameters)
            pending_action.execution_result = result
            state.step_history.append(
                f"Tools (Autonomous): Ran '{pending_action.tool_name}' -> Found {len(result.splitlines())} lines."
            )
            return state

        # Case B: WRITE TOOL (Guarded by Human-in-the-Loop)
        if pending_action.tool_type == "write":
            # 1. Has the human responded yet?
            if state.human_approved is None:
                # Pause execution! Wait for the UI button click.
                state.requires_approval = True
                state.step_history.append(
                    f"Tools (GATE PAUSED): Proposed '{pending_action.tool_name}' with parameters {pending_action.parameters}. "
                    "Waiting for engineer approval."
                )
                return state

            # 2. Human clicked APPROVED
            elif state.human_approved is True:
                state.requires_approval = False
                if pending_action.tool_name == "draft_jira_ticket":
                    result = draft_jira_ticket(**pending_action.parameters)
                else:
                    result = execute_remediation_command(**pending_action.parameters)

                pending_action.execution_result = result
                state.step_history.append(
                    f"Tools (APPROVED & EXECUTED): Ran '{pending_action.tool_name}' -> Result:\n{result}"
                )
                return state

            # 3. Human clicked REJECTED
            else:
                state.requires_approval = False
                state.step_history.append(
                    f"Tools (REJECTED BY HUMAN): Aborted '{pending_action.tool_name}' per engineer instructions."
                )
                return state

        return state
