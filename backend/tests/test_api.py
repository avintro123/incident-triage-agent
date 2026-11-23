# ==============================================================================
# Quick Test Script for FastAPI Backend Endpoints
# Run this to verify Step 15 works!
# ==============================================================================

from fastapi.testclient import TestClient
from backend.main import app, hybrid_store, parser

print("--- Testing FastAPI Backend Server ---")

# Pre-load sample runbook cards so the store is populated
sample_runbook = "data/sample_docs/runbook_redis_cluster.md"
cards = parser.parse_file(sample_runbook)
hybrid_store.index_cards(cards)

# Create the test client
client = TestClient(app)

# ------------------------------------------------------------------------------
# Test 1: Health Check Endpoint
# ------------------------------------------------------------------------------
print("\n1. Testing GET /api/health:")
response = client.get("/api/health")
print(f"   Status Code: {response.status_code}")
print(f"   Response:    {response.json()}")

assert response.status_code == 200
assert response.json()["status"] == "healthy"
assert response.json()["docs_indexed"] > 0

# ------------------------------------------------------------------------------
# Test 2: Synchronous Diagnosis Endpoint
# ------------------------------------------------------------------------------
print("\n2. Testing POST /api/triage/diagnose:")
payload = {
    "incident_report": "API gateway throwing 504 on checkout. REDIS_MEM_CRITICAL alert triggered."
}
response = client.post("/api/triage/diagnose", json=payload)
data = response.json()

print(f"   Status Code:    {response.status_code}")
print(f"   Citations:      {data.get('citations')}")
print(f"   Final Output:\n   {data.get('final_output')[:100]}...\n")

assert response.status_code == 200
assert "final_output" in data
assert len(data["citations"]) > 0
assert len(data["step_history"]) >= 4

# ------------------------------------------------------------------------------
# Test 3: Server-Sent Events (SSE) Streaming Endpoint
# ------------------------------------------------------------------------------
print("3. Testing POST /api/triage/stream (SSE Stream):")
response = client.post("/api/triage/stream", json=payload)

print(f"   Status Code:  {response.status_code}")
print(f"   Content-Type: {response.headers.get('content-type')}")

# Read the streamed chunks
chunks = response.text.strip().split("\n\n")
print(f"   Received {len(chunks)} SSE Event Chunks:")
for i, chunk in enumerate(chunks[:4], 1):
    print(f"     Event #{i}: {chunk[:80]}...")

assert response.status_code == 200
assert "text/event-stream" in response.headers.get("content-type", "")
assert len(chunks) >= 5
assert any("init" in c for c in chunks)
assert any("complete" in c for c in chunks)

print("\nSUCCESS: All FastAPI endpoints (Health, Diagnose, and Live SSE Streaming) passed flawlessly!")
