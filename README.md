# agent_app

Autonomous document-generation API. Given a plain-English request, it plans, writes, and saves a `.docx` file.

---

## Architecture

```
POST /agent
    │
    ▼
generate_plan()          planner.py
    │  LLM picks doc_type, title, assumptions, 4-7 ordered steps
    ▼
execute_plan()           executor.py
    │  LLM writes 2-4 prose paragraphs per step (one call per section)
    ▼
build_docx()             doc_builder.py
    │  python-docx assembles title block + assumptions + sections
    ▼
outputs/<slug>_<YYYYMMDD>_<HHMMSS>.docx
```

**Why Planner → Executor over ReAct (observe-act loops)?**
ReAct is powerful when the agent must discover what to do next based on tool output. Here the task is fully specified upfront: produce one structured document. A single planning call followed by parallel-friendly section calls is deterministic, debuggable, and completes in ~15 s — no loop convergence risk, no runaway token spend.

---

## Resilience: Retry & Fallback

**What:**
- `llm_client.call_llm` retries up to 3 times with exponential backoff (`2^attempt` seconds: 0 s, 2 s, 4 s) and returns `None` on final failure rather than raising.
- `generate_plan` falls back to a hardcoded 3-step (Introduction / Details / Conclusion) `AgentPlan` when the LLM is unavailable or returns unparseable JSON.
- `execute_plan` substitutes `"Content unavailable for this section — see assumptions."` for any section whose LLM call returns `None`, so the document is always structurally complete.

**Why:** Partial success beats total failure. A document with one placeholder section is more useful to the caller than an HTTP 500. The fallback also makes the API testable without a live Groq key.

**Impact:** The API returns a valid `AgentResponse` and a valid `.docx` file in all reachable failure modes except a complete infrastructure outage (handled by the 500 wrapper in `main.py`).

---

## Run

```bash
cd agent_app
pip install -r requirements.txt

uvicorn main:app --reload
```

Endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Liveness check |
| `POST` | `/agent` | Run the full pipeline |
| `GET`  | `/agent/download/{filename}` | Download a generated `.docx` |

---

## Test Inputs

**1. Specific, well-scoped request**
```bash
curl -X POST localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"request":"Create a project plan for migrating our internal CRM to a new platform"}'
```
Demonstrates: planner chooses `project plan`, generates 6-7 domain-accurate sections (current-state assessment, data migration strategy, go-live plan), assumptions are minimal because the request is clear.

**2. Vague, under-specified request**
```bash
curl -X POST localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"request":"We had a meeting about the new feature but I do not remember all the details, just write something up"}'
```
Demonstrates: planner chooses `meeting minutes`, surfaces explicit assumptions (`"The meeting was attended by key stakeholders"`, `"Action items were assigned to attendees"`) to fill gaps the user left open. The document is still fully generated — assumptions are visible in the response and embedded in the `.docx`.

---

## Tradeoff: Autonomous Planning vs Deterministic Workflows

The planner has genuine autonomy: it freely selects `doc_type` from seven options and names sections however it judges appropriate. That flexibility is what makes the API useful across diverse requests.

The constraint is the Pydantic schema. Every plan must fit `AgentPlan` (typed fields, `list[TaskStep]`, required `step_id`/`title`/`description`/`section_heading`). This means:

- **Pro:** The executor and doc-builder never receive malformed data; the pipeline is composable and testable at each boundary.
- **Con:** The LLM cannot express structure that falls outside the schema — e.g. nested sub-sections, tables of decisions, or appendices. Extending the output format requires a schema change and a corresponding doc-builder update.

The sweet spot for production: keep the schema as the stable contract, and expand it deliberately when a new document type genuinely needs richer structure.
