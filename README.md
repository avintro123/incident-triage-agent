# Incident Triage Agent 🚨

An autonomous, self-correcting Agentic RAG platform that ingests messy technical documentation, architecture runbooks, and repository logs to diagnose production outages, cite exact sources, and propose validated remediation steps with human-in-the-loop approval.

---

## 🎯 Architecture & Features
* **Structure-Aware Chunking:** Parses Markdown runbooks and technical docs along heading boundaries, keeping diagnostic tables and terminal commands whole.
* **Token Budget Economics:** Dynamic token counting and context pruning prevents prompt overflow and "Lost-in-the-Middle" latency degradation.
* **Hybrid Search (BM25 + Dense Vectors):** Combines exact keyword matching (for error codes like `ERR_OOM_COMMAND_NOT_ALLOWED`) with dense vector semantic search, merged via Reciprocal Rank Fusion (RRF).
* **Self-Correcting LangGraph Engine:** Cyclic state machine with retrieval grading, autonomous query reformulation loops, and human-in-the-loop approval gates.
* **Strict Inline Citations:** Verifiable source receipts citing filename, section headers, and page numbers.

---

## 🛠️ Tech Stack
* **LLM & Embeddings:** Google Gemini (`gemini-2.5-flash`, `text-embedding-004`)
* **Agent Framework:** LangGraph & LangChain
* **Vector Store:** Qdrant
* **Keyword Matching:** Rank-BM25
* **Backend:** FastAPI (Python 3.12)
* **Package Management:** `uv`

