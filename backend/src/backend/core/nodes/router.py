# ==============================================================================
# Step 10: Node 1 — The Query Router & Sub-query Planner
# File: backend/src/backend/core/nodes/router.py
#
# FOR BEGINNERS:
# When an outage happens, the human or monitoring bot reports a messy paragraph.
# Node 1 acts like the triage doctor in an emergency room:
# 1. Reads the complaint.
# 2. Extracts the exact symptoms, error codes, and service names.
# 3. Splits the complaint into 1 to 3 targeted search queries.
# 4. Decides whether to search Runbooks, search Logs, or ask for more info!
# ==============================================================================

import os
import re
import logging
from typing import List, Optional
from pydantic import BaseModel, Field

# Import our Case File blueprint from Step 9
from backend.core.state import AgentState

logger = logging.getLogger(__name__)


class PlanOutput(BaseModel):
    """
    Structured output format that we ask Gemini to return.
    Using Pydantic guarantees that the AI returns clean data rather than
    random conversational banter.
    """
    route: str = Field(
        description="Where to look: 'search_runbooks', 'search_logs', or 'ask_clarification'"
    )
    sub_queries: List[str] = Field(
        description="1 to 3 concise, keyword-rich queries to search our internal documentation"
    )
    reasoning: str = Field(
        description="Brief explanation of why this plan was chosen"
    )


class QueryRouterNode:
    """
    Node 1 in the LangGraph State Machine:
    The Lead Investigator that plans the search strategy.
    """

    def __init__(
        self,
        google_api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash"
    ):
        self.google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name
        self.llm = None

        # If a Gemini API key is present, initialize the LLM
        if self.google_api_key:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self.llm = ChatGoogleGenerativeAI(
                    model=self.model_name,
                    google_api_key=self.google_api_key,
                    temperature=0.0  # Zero temperature for deterministic, factual planning
                )
            except Exception as e:
                logger.warning(f"Could not load Gemini in RouterNode: {e}")

    def __call__(self, state: AgentState) -> AgentState:
        """
        Executes Node 1:
        Reads state.incident_report -> Generates plan -> Updates state.sub_queries.
        """
        logger.info(f"Node 1 (Router): Planning search for report: '{state.incident_report[:60]}...'")

        # 1. Ask Gemini to break down the incident report
        plan = self._generate_plan(state.incident_report)

        # 2. Update our Case File (State)
        state.sub_queries = plan.sub_queries
        state.step_history.append( 
            f"Router/Planner: Selected route '{plan.route}' with {len(plan.sub_queries)} sub-queries: {plan.sub_queries}"
        )

        return state

    def _generate_plan(self, report: str) -> PlanOutput:
        """
        Calls Gemini to break down the report, or uses our smart fallback
        if testing offline without an API key.
        """
        if self.llm:
            try:
                # Use LangChain with structured output
                structured_llm = self.llm.with_structured_output(PlanOutput)
                prompt = (
                    "You are a Senior Site Reliability Engineer (SRE) triaging a production outage.\n"
                    "Analyze this incident report and break it into 1 to 3 targeted search queries.\n"
                    "Extract exact error codes (e.g. ERR_OOM_504, 504), service names (e.g. Redis, PgBouncer), "
                    "and core symptoms.\n\n"
                    f"Incident Report: {report}"
                )
                return structured_llm.invoke(prompt)
            except Exception as e:
                logger.warning(f"Gemini planning call failed ({e}), using local rule-based planner.")

        # --- Smart Offline Fallback (For offline unit tests) ---
        return self._local_rule_based_planner(report)

    def _local_rule_based_planner(self, report: str) -> PlanOutput:
        """
        Rule-based planner that extracts error codes, HTTP codes, and tech keywords
        so unit tests pass without needing a live internet connection or API key.
        """
        report_lower = report.lower()

        # If report is too vague, ask for clarification
        if len(report.strip()) < 10 or report_lower in ["it's broken", "help", "error"]:
            return PlanOutput(
                route="ask_clarification",
                sub_queries=[],
                reasoning="Incident report is too vague to search for solutions."
            )

        # Extract technical tokens: error codes, HTTP numbers (500, 502, 504), service names
        error_codes = re.findall(r"[A-Z0-9_]{4,}", report)  # e.g. REDIS_MEM_CRITICAL, ERR_OOM
        http_codes = re.findall(r"\b[45]\d{2}\b", report)   # e.g. 500, 502, 504
        
        queries: List[str] = []

        # Sub-query 1: Specific error codes
        if error_codes:
            queries.append(" ".join(error_codes))

        # Sub-query 2: HTTP status codes + affected components
        components = [w for w in ["redis", "postgres", "pgbouncer", "checkout", "auth", "api", "database", "gateway"] if w in report_lower]
        if http_codes or components:
            parts = http_codes + components
            queries.append(" ".join(parts))

        # If nothing specific was matched, use the cleaned original text
        if not queries:
            clean_query = re.sub(r"[^a-zA-Z0-9\s]", " ", report).strip()
            queries.append(clean_query[:80])

        return PlanOutput(
            route="search_runbooks",
            sub_queries=queries[:3],
            reasoning="Extracted high-priority technical identifiers and component names."
        )
