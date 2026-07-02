# ModifAI — Project Update 1

**Date:** 30 June 2026
**Milestone:** LangGraph Orchestration Backbone — Complete

---

## What Is ModifAI?

ModifAI is a production-grade **multi-agent AI platform** being built to automate the full ML lifecycle:

> Upload documents → Extract text → Chunk → Generate dataset → Quality check → Fine-tune → Evaluate → Deploy

The platform is designed so that every step is an independent AI agent, and a central orchestration layer (LangGraph) controls all execution flow.

---

## What We Built in This Update

We did **not** implement any AWS services, OCR engines, or LLM calls yet.

Instead, we built the **entire orchestration backbone** that every future real agent will plug into. This is Milestone 1.

---

## Technology Stack

| Technology | Role |
|---|---|
| **Python 3.13** | Core language |
| **LangGraph** | Multi-agent graph orchestration (`StateGraph`) |
| **LangChain Core** | Runnable interface compatibility |
| **Pydantic v2** | Input validation at the pipeline entry point |
| **pytest** | Automated smoke testing |

---

## Project Folder Structure

```
MODIFAINEW1/
│
├── app.py                    ← Entry point — 3 runnable demo scenarios
├── requirements.txt          ← Pinned dependencies
├── README.md                 ← Full documentation + Mermaid workflow diagram
│
├── config/
│   └── settings.py           ← Frozen global settings (thresholds, log level)
│
├── graph/
│   ├── state.py              ← ModifAIState — the shared pipeline state (TypedDict)
│   ├── graph_builder.py      ← build_graph() — single source of topology
│   └── routers.py            ← 4 pure conditional routing functions
│
├── agents/
│   ├── validation.py         ← Validates prompt, detects OCR requirement
│   ├── ocr.py                ← Extracts text from uploaded documents (stub)
│   ├── chunking.py           ← Splits documents into chunks (stub)
│   ├── generation.py         ← Generates training dataset (stub)
│   ├── quality.py            ← Scores dataset quality (stub)
│   ├── finetune.py           ← Submits fine-tuning job (stub)
│   ├── evaluation.py         ← Evaluates trained model (stub)
│   └── deployment.py         ← Deploys model to endpoint (stub)
│
├── schemas/
│   └── state_schema.py       ← Pydantic input schema + to_initial_state()
│
├── utils/
│   ├── logger.py             ← Centralised logger factory (get_logger)
│   └── node_helpers.py       ← Shared enter/leave/build_base_update helpers
│
└── tests/
    └── test_graph.py         ← 22 automated smoke tests
```

---

## The Pipeline Workflow

```
START
  │
  ▼
Initialize State
  │
  ▼
Validation Agent
  │
  ├── Invalid ──────────────────────────────────────────► END
  │
  ▼
Router
  │
  ├── ocr_required = True ──► OCR Agent ──┐
  │                                       │
  └── ocr_required = False ───────────────┤
                                          ▼
                                  Chunking Agent
                                          │
                                          ▼
                                Dataset Generation Agent
                                          │
                                          ▼
                                Dataset Quality Agent
                                          │
                          quality >= 0.85 ?
                           │              │
                          YES             NO
                           │              │
                           ▼              └──► Dataset Generation Agent (retry)
                     Fine-Tune Agent
                           │
                           ▼
                     Evaluation Agent
                           │
                     metrics pass ?
                       │         │
                      YES        NO
                       │         │
                       ▼         └──► Fine-Tune Agent (retry)
                 Deployment Agent
                       │
                       ▼
                      END
```

---

## Shared State — `ModifAIState`

The entire pipeline revolves around a single shared state object. Every agent reads from it and returns **only the fields it updates**. LangGraph merges partial updates automatically.

### Fields

| Field | Type | Set By |
|---|---|---|
| `session_id` | `str` | Entry point |
| `user_prompt` | `str` | Entry point |
| `uploaded_files` | `List[str]` | Entry point |
| `dataset_type` | `Optional[str]` | Validation Agent |
| `task_type` | `Optional[str]` | Validation Agent |
| `validation_status` | `Optional[bool]` | Validation Agent |
| `ocr_required` | `bool` | Validation Agent |
| `extracted_documents` | `List[str]` | OCR Agent |
| `chunks` | `List[str]` | Chunking Agent |
| `generated_dataset` | `List[dict]` | Dataset Generation Agent |
| `dataset_quality_score` | `float` | Dataset Quality Agent |
| `training_job_id` | `Optional[str]` | Fine-Tune Agent |
| `training_status` | `Optional[str]` | Fine-Tune Agent |
| `model_uri` | `Optional[str]` | Fine-Tune Agent |
| `evaluation_metrics` | `Dict[str, Any]` | Evaluation Agent |
| `deployment_url` | `Optional[str]` | Deployment Agent |
| `current_agent` | `str` | Every agent |
| `execution_history` | `List[str]` *(append)* | Every agent |
| `errors` | `List[str]` *(append)* | Any agent on failure |
| `metadata` | `Dict[str, Any]` | Extensibility bag |

> `execution_history` and `errors` use LangGraph's `operator.add` reducer — each node **appends** to the list rather than replacing it.

---

## Conditional Routing — 4 Decision Points

| Location | Condition | Route |
|---|---|---|
| After **Validation Agent** | `validation_status == False` | `END` (early termination) |
| After **Validation Agent** | `validation_status == True` | `Router` node |
| **Router** | `ocr_required == True` | OCR Agent |
| **Router** | `ocr_required == False` | Chunking Agent (skip OCR) |
| After **Quality Agent** | `score >= 0.85` | Fine-Tune Agent |
| After **Quality Agent** | `score < 0.85` | Dataset Generation Agent (retry loop) |
| After **Evaluation Agent** | metrics pass | Deployment Agent |
| After **Evaluation Agent** | metrics fail | Fine-Tune Agent (retry loop) |

All routing is handled by pure functions in `graph/routers.py`. No `if/else` in the graph builder.

---

## Architecture Principles Applied

| Principle | How It Was Applied |
|---|---|
| **Single Responsibility** | Each agent has exactly one job |
| **Open/Closed** | Adding a new agent requires only a new file + one line in `graph_builder.py` |
| **Separation of Concerns** | Routing logic (`routers.py`) is separate from topology (`graph_builder.py`) and business logic (`agents/`) |
| **DRY** | `node_helpers.py` eliminates copy-paste enter/exit/history boilerplate across all 8 agents |
| **Fail-Safe** | Every agent wraps its work in `try/except`; errors append to `state.errors` and execution continues gracefully |
| **Type Safety** | Full type hints everywhere; Pydantic validates inputs; `Literal` return types on routing functions |

---

## Demo Scenarios Verified

### Scenario 1 — Standard pipeline (no OCR)

```
Input:  user_prompt = "Generate a QA dataset from our internal knowledge base."
        uploaded_files = ["knowledge_base.txt"]

Execution Path (9 steps):
   1. Initialize State
   2. Validation Agent
   3. Router
   4. Chunking Agent          ← skips OCR (text file)
   5. Dataset Generation Agent
   6. Dataset Quality Agent   ← score 0.920 >= 0.85, PASS
   7. Fine-Tune Agent         ← job id: modifai-job-XXXXXXXX
   8. Evaluation Agent        ← accuracy 0.92 >= 0.80, PASS
   9. Deployment Agent        ← URL: https://api.modifai.ai/v1/endpoints/...
```

### Scenario 2 — OCR path (PDF uploaded)

```
Input:  user_prompt = "Extract and fine-tune on the contents of this annual report."
        uploaded_files = ["annual_report_2024.pdf"]

Execution Path (10 steps):
   1. Initialize State
   2. Validation Agent        ← detects .pdf → ocr_required = True
   3. Router                  ← routes to OCR Agent
   4. OCR Agent               ← extracts text from PDF
   5. Chunking Agent
   6. Dataset Generation Agent
   7. Dataset Quality Agent
   8. Fine-Tune Agent
   9. Evaluation Agent
  10. Deployment Agent
```

### Scenario 3 — Validation failure (blank prompt)

```
Input:  user_prompt = "   "  (whitespace only)

Result: Pydantic raises ValidationError BEFORE the graph is invoked.
        Graph never runs. Zero cost.
```

---

## Test Results

```
22 passed in 0.27s
```

| Test Class | Tests | Covers |
|---|---|---|
| `TestGraphBuildsSuccessfully` | 2 | Graph compiles, independent instances |
| `TestHappyPath` | 11 | Deployment URL, execution history, all metric keys, error-free run |
| `TestOCRPath` | 4 | OCR Agent in history, extracted_documents, ocr_required flag |
| `TestValidationFailurePath` | 4 | Early exit, training/deployment fields stay None, history trimmed |

---

## Configuration

All tunable values live in `config/settings.py`:

| Setting | Default | Purpose |
|---|---|---|
| `QUALITY_THRESHOLD` | `0.85` | Minimum dataset quality to proceed to fine-tuning |
| `EVAL_PASS_THRESHOLD` | `0.80` | Minimum model accuracy to proceed to deployment |
| `MAX_RETRY_LOOPS` | `3` | Safety cap on retry loops (informational) |
| `LOG_LEVEL` | `"INFO"` | Python logging level |

---

## Run Commands

```bash
# Run the 3 demo scenarios
python -X utf8 app.py

# Run the full test suite
python -X utf8 -m pytest tests/ -v
```

---

## What Is NOT Done Yet (Next Milestones)

| Feature | Status | Notes |
|---|---|---|
| OCR (AWS Textract) | Stub only | Replace `agents/ocr.py` internals |
| Dataset Generation (Amazon Bedrock) | Stub only | Replace `agents/generation.py` internals |
| Quality Scoring (LLM-as-judge) | Stub only | Replace `agents/quality.py` internals |
| Fine-Tuning (Amazon SageMaker) | Stub only | Replace `agents/finetune.py` internals |
| Evaluation (Batch inference + metrics) | Stub only | Replace `agents/evaluation.py` internals |
| Deployment (SageMaker Endpoint) | Stub only | Replace `agents/deployment.py` internals |
| LangSmith tracing | Not started | Add tracing callbacks to graph invoke |
| API layer (FastAPI) | Not started | Expose `run_pipeline()` as an HTTP endpoint |
| Persistent state (DynamoDB / S3) | Not started | Add checkpointer to `build_graph()` |
| Authentication & multi-tenancy | Not started | Session isolation per user |

---

## How to Add the Next Real Agent

When you're ready to replace a stub with a real implementation:

1. Add any new state fields to `graph/state.py` → `ModifAIState`
2. Replace the stub logic inside the relevant `agents/` file
3. Add any new AWS credentials/config to `config/settings.py`
4. **No other file needs to change** — the graph wiring, routing, logging, and test fixtures are all already in place
