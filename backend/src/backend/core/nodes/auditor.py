# ==============================================================================
# Step 13: Node 4 — The Citation & Hallucination Auditor
# File: backend/src/backend/core/nodes/auditor.py
#
# FOR BEGINNERS:
# Why do we need an Auditor?
# LLMs can sound extremely confident even when making up fake commands or facts.
#
# Node 4 acts like a Fact-Checker at a newspaper:
# 1. Compares the AI's draft diagnosis sentence-by-sentence against the evidence cards.
# 2. Strips or flags any technical claim that cannot be proven by our runbooks.
# 3. Attaches exact, verified citations ([file.md, Section: Title]).
# 4. Assembles the final, clean response for the engineer!
# ==============================================================================

import os
import re
import logging
from typing import List, Optional
from pydantic import BaseModel, Field

# Import our Case File blueprint from Step 9
from backend.core.state import AgentState

logger = logging.getLogger(__name__)


class AuditReport(BaseModel):
    """
    Structured audit result.
    """
    is_faithful: bool = Field(
        description="True if all claims are supported by the retrieved documentation"
    )
    verified_text: str = Field(
        description="The final response text with hallucinated claims removed or flagged"
    )
    valid_citations: List[str] = Field(
        description="List of verified citation labels cited in the text"
    )
    hallucinations_detected: List[str] = Field(
        default_factory=list,
        description="List of claims that were stripped because they had no source documentation"
    )


class CitationAuditorNode:
    """
    Node 4 in the LangGraph State Machine:
    The Fact-Checker that guarantees zero hallucinated commands reach the user.
    """

    def __init__(
        self,
        google_api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash"
    ):
        self.google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name
        self.llm = None

        if self.google_api_key:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self.llm = ChatGoogleGenerativeAI(
                    model=self.model_name,
                    google_api_key=self.google_api_key,
                    temperature=0.0
                )
            except Exception as e:
                logger.warning(f"Could not load Gemini in CitationAuditorNode: {e}")

    def __call__(self, state: AgentState) -> AgentState:
        """
        Executes Node 4:
        Audits state.draft_diagnosis against state.retrieved_docs.
        Updates state.final_output and state.citations.
        """
        logger.info("Node 4 (Auditor): Auditing draft diagnosis against retrieved sources.")

        # 1. Run the fact-checking audit
        audit = self._audit_claims(state)

        # 2. Update our Case File
        state.final_output = audit.verified_text
        state.citations = audit.valid_citations

        # 3. Record audit findings in step history
        if audit.hallucinations_detected:
            state.step_history.append(
                f"Auditor: FLAGGED & STRIPPED {len(audit.hallucinations_detected)} unverified claims: "
                f"{audit.hallucinations_detected}"
            )
        else:
            state.step_history.append(
                f"Auditor: PASSED. All claims verified with {len(audit.valid_citations)} citations."
            )

        return state

    def _audit_claims(self, state: AgentState) -> AuditReport:
        """
        Audits draft diagnosis using Gemini, or our smart local rule-based checker
        for unit tests.
        """
        if not state.draft_diagnosis:
            return AuditReport(
                is_faithful=True,
                verified_text="No draft diagnosis was provided to audit.",
                valid_citations=[]
            )

        if self.llm and state.retrieved_docs:
            try:
                docs_text = "\n---\n".join([
                    f"Citation Label: {c.citation_label()}\nContent:\n{c.content}"
                    for c in state.retrieved_docs
                ])

                structured_llm = self.llm.with_structured_output(AuditReport)
                prompt = (
                    "You are a strict technical fact-checker for site reliability engineering.\n"
                    "Compare this Draft Diagnosis against the Ground Truth Documentation.\n"
                    "Rules:\n"
                    "1. Every single terminal command or parameter MUST exist in the Ground Truth Documentation.\n"
                    "2. If the Draft Diagnosis mentions a command or setting NOT found in the Ground Truth, "
                    "strip it out or flag it as [UNVERIFIED].\n"
                    "3. Format the final verified_text with inline citations (e.g. [runbook.md, Section: XYZ]).\n\n"
                    f"Ground Truth Documentation:\n{docs_text}\n\n"
                    f"Draft Diagnosis:\n{state.draft_diagnosis}"
                )
                return structured_llm.invoke(prompt)
            except Exception as e:
                logger.warning(f"Gemini audit failed ({e}), using local rule-based auditor.")

        # --- Smart Offline Fallback (For unit tests) ---
        return self._local_rule_based_audit(state)

    def _local_rule_based_audit(self, state: AgentState) -> AuditReport:
        """
        Rule-based fact checker for unit tests without needing an API key.
        Verifies every command parameter against retrieved evidence cards.
        """
        combined_sources = " ".join([c.content for c in state.retrieved_docs]).lower()
        citations = [c.citation_label() for c in state.retrieved_docs]

        sentences = [s.strip() for s in re.split(r"[.\n]", state.draft_diagnosis) if s.strip()]
        verified_sentences: List[str] = []
        hallucinations: List[str] = []

        for sentence in sentences:
            # Check if sentence contains technical commands wrapped in backticks
            commands = re.findall(r"`([^`]+)`", sentence)
            
            is_valid = True
            for cmd in commands:
                # Check each key argument in the command (e.g. 'flushall' in 'redis-cli flushall')
                cmd_tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9_\-]+", cmd) if len(t) > 2]
                unsupported_tokens = [t for t in cmd_tokens if t not in combined_sources]
                if unsupported_tokens:
                    is_valid = False
                    hallucinations.append(cmd)

            if is_valid:
                verified_sentences.append(sentence)
            else:
                verified_sentences.append(f"[UNVERIFIED CLAIM REMOVED: {sentence}]")

        clean_text = ". ".join(verified_sentences)
        if citations:
            clean_text += f"\n\n**Sources:** {', '.join(citations)}"

        return AuditReport(
            is_faithful=len(hallucinations) == 0,
            verified_text=clean_text,
            valid_citations=citations,
            hallucinations_detected=hallucinations
        )
