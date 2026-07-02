# ModifAI — Agent Development Guide

> **Audience:** Developers implementing individual agents for the ModifAI ML pipeline.
> This document is the **authoritative integration contract**. Deviations will break the shared graph.

---

## Agent Interface Specification

These four rules are non-negotiable. Every agent, without exception, must comply.

| # | Rule |
|---|------|
| 1 | **Read only** the `ModifAIState` fields your agent requires. |
| 2 | **Write only** the `ModifAIState` fields your agent owns (see [State Ownership Table](#10-state-ownership-table)). |
| 3 | **Never call another agent directly.** The LangGraph orchestrator owns execution order. |
| 4 | **Always return the shared state dict**, even when processing fails — record errors in `errors`. |

Violating any of these rules will corrupt the shared state and break the pipeline for every downstream agent.

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [Agent Responsibilities](#2-agent-responsibilities)
3. [Agent Contract](#3-agent-contract)
4. [Shared State Guidelines](#4-shared-state-guidelines)
5. [Coding Standards](#5-coding-standards)
6. [Logging Standards](#6-logging-standards)
7. [Error Handling](#7-error-handling)
8. [Agent Template](#8-agent-template)
9. [Folder Structure](#9-folder-structure)
10. [State Ownership Table](#10-state-ownership-table)
11. [Integration Checklist](#11-integration-checklist)
12. [Definition of Done](#12-definition-of-done)

---

## 1. Purpose

The LangGraph orchestration backbone (`graph/graph_builder.py`) is **already implemented and frozen**. It defines the graph topology: which nodes exist, in what order they execute, and what conditional routing logic governs transitions.

Your responsibility is to implement the **internal logic** of your assigned agent only. Specifically:

- Read the required input fields from `ModifAIState`.
- Execute your agent's single responsibility.
- Return a **partial dict** containing only the fields your agent owns.

You do **not** own and must **not** touch:

- `graph/graph_builder.py` — graph topology
- `graph/routers.py` — conditional routing functions
- `graph/state.py` — the `ModifAIState` TypedDict definition
- Any other agent's file

If you believe a state field is missing or a routing rule is wrong, raise it with the orchestration lead — do not modify those files unilaterally.

---

## 2. Agent Responsibilities

Every agent follows the **Single Responsibility Principle**. One agent performs exactly one task. There is no exception.

| Agent | Single Responsibility |
|---|---|
| **Validation Agent** | Validates the user prompt and classifies `dataset_type`, `task_type`, and `ocr_required`. |
| **OCR Agent** | Extracts raw text from uploaded documents (PDF, images). |
| **Chunking Agent** | Splits extracted documents into fixed-size text chunks with overlap. |
| **Dataset Generator** | Generates structured training examples from text chunks. |
| **Quality Agent** | Scores the generated dataset and sets `dataset_quality_score`. |
| **Fine-Tuning Agent** | Submits a fine-tuning job and records `training_job_id`, `training_status`, `model_uri`. |
| **Evaluation Agent** | Evaluates the trained model and records `evaluation_metrics`. |
| **Deployment Agent** | Deploys the model to an endpoint and records `deployment_url`. |

If your agent is doing two things, split it or raise a design discussion. Multi-responsibility agents are rejected at code review.

---

## 3. Agent Contract

All agents share the same function signature and lifecycle. This is the contract that makes parallel development safe.

### 3.1 Function Signature

```python
def <agent_name>_agent(state: ModifAIState) -> dict:
```

The function receives the **full** shared state and returns a **partial** dict. LangGraph merges the returned dict back into the live state automatically.

### 3.2 Inputs

- The only parameter is `state: ModifAIState`.
- Read fields using `state.get("field_name", <default>)` — never index directly (`state["field"]`) as missing keys will raise `KeyError`.
- Read **only** the fields your agent requires (see [State Ownership Table](#10-state-ownership-table)).
- Treat all other fields as read-only; do not inspect or branch on them.

```python
# CORRECT
chunks: list = state.get("chunks", [])

# WRONG — indexing raises KeyError if field is absent
chunks = state["chunks"]

# WRONG — reading a field your agent does not own
score = state.get("dataset_quality_score")  # belongs to Quality Agent
```

### 3.3 Outputs

- Return a `dict` containing **only** the fields your agent owns.
- Always start your return dict from `build_base_update("Your Agent Name")`, which handles `current_agent` and `execution_history` for you.
- Never include fields owned by another agent in your return dict.

```python
# CORRECT — Fine-Tune Agent returns only its fields
update = build_base_update("Fine-Tune Agent")
update["training_job_id"] = job_id
update["training_status"] = "COMPLETED"
update["model_uri"] = model_uri
return update

# WRONG — writing a field owned by a different agent
update["deployment_url"] = "..."  # owned by Deployment Agent
```

### 3.4 Appending vs. Replacing

Two fields use the `operator.add` reducer in `ModifAIState` — meaning LangGraph **appends** your returned list to the existing list rather than replacing it:

| Field | Reducer | How to write |
|---|---|---|
| `execution_history` | append | Handled automatically by `build_base_update` |
| `errors` | append | `update["errors"] = ["YourAgent: message"]` |

All other fields use the **replace** reducer (last write wins). Assign them as scalar values or complete lists, not deltas.

### 3.5 Return Value

Always return `update` — even when an error occurs. The orchestrator must receive a dict to continue routing.

```python
# Error path — still return the update
except Exception as exc:
    update["errors"] = [f"MyAgent: {exc}"]
return update  # never omit this
```

---

## 4. Shared State Guidelines

`ModifAIState` (defined in `graph/state.py`) is the **single source of truth** for all agents. Treat it as an append-only ledger during a pipeline run.

### Rules

| Rule | Detail |
|---|---|
| **Never delete fields** | Do not `del state["field"]` or return a dict that omits existing keys with intent to clear them. |
| **Never rename fields** | If a field name needs to change, coordinate with the orchestration lead — it requires a schema change across the entire graph. |
| **Never modify fields owned by another agent** | The ownership table is authoritative. If you need a value that does not exist, request a new field. |
| **Never reset the state** | Do not return a complete copy of the state with fields zeroed out. Only return what you changed. |
| **Only update your assigned outputs** | Your diff against the state should touch exactly the fields listed in your row of the ownership table, plus `current_agent` and `execution_history`. |

### Examples

```python
# CORRECT — Chunking Agent writes only its field
update["chunks"] = ["chunk 1", "chunk 2", "chunk 3"]

# WRONG — clearing a field you did not create
update["extracted_documents"] = []   # owned by OCR Agent

# WRONG — resetting orchestration metadata
update["execution_history"] = []     # managed by LangGraph + build_base_update

# WRONG — renaming a field in your return dict
update["text_chunks"] = [...]        # state field is "chunks", not "text_chunks"
```

### Adding a New Field

If your agent genuinely needs a field that does not yet exist in `ModifAIState`:

1. Open a discussion with the orchestration lead.
2. The field is added to `graph/state.py` and `schemas/state_schema.py`.
3. The `to_initial_state()` method is updated with a null default.
4. **You do not make those changes yourself.**

---

## 5. Coding Standards

All agent files must comply with the following standards. PRs that violate them are blocked.

### 5.1 Type Hints

All function parameters and return types must be annotated.

```python
def chunking_agent(state: ModifAIState) -> dict:
    chunks: list[str] = state.get("chunks", [])
```

### 5.2 Docstrings — Google Style

Every public function and class requires a Google-style docstring.

```python
def my_agent(state: ModifAIState) -> dict:
    """One-line summary of what this agent does.

    Args:
        state: The current shared pipeline state.

    Returns:
        A partial state dict containing only the fields updated by this agent.
    """
```

### 5.3 PEP 8

- Maximum line length: **99 characters**.
- Use `black` for formatting, `isort` for import ordering.
- Run `flake8` before committing.

### 5.4 Modularity

- Keep business logic in private helper functions (`_extract_text`, `_score_dataset`, etc.).
- The public `<name>_agent(state)` function should be a thin orchestrator of those helpers.
- Do not put hundreds of lines of logic directly inside `<name>_agent`.

### 5.5 Determinism

- Prefer deterministic outputs wherever possible.
- If randomness is required (e.g., sampling), accept a seed parameter or read it from `state["metadata"]`.
- Non-deterministic agents are harder to test and harder to debug.

### 5.6 No Global Variables

- Do not store mutable state in module-level variables.
- Module-level **constants** (uppercase, immutable) are acceptable.

```python
# Acceptable constant
_MODEL_S3_PREFIX = "s3://modifai-models/stub"

# WRONG — mutable global; state leaks between invocations
_cached_result = {}
```

### 5.7 Separation of Concerns

- Business logic must not import from `graph/` (except `graph.state.ModifAIState` for the type hint).
- Orchestration concerns (logging entry/exit, building the base update dict) are handled by `utils/node_helpers.py` — use the provided helpers, do not reimplement them.

---

## 6. Logging Standards

Every agent uses the centralised logger factory. Import it as follows:

```python
from utils.logger import get_logger
logger = get_logger(__name__)
```

### Required Log Points

Every agent **must** emit log messages at these lifecycle points:

| Lifecycle Point | How | Example Message |
|---|---|---|
| **Agent entered** | `enter_node(...)` helper | `Entering OCR Agent...` |
| **Input summary** | `logger.info` after reading state | `Processing 3 file(s) via OCR...` |
| **Processing** | `logger.info` during work | `  Extracted 3 document(s).` |
| **Output summary** | captured by `leave_node(...)` helper | *(automatic — fields returned by node)* |
| **Agent exited** | `leave_node(...)` helper | `Leaving OCR Agent.` |
| **Errors** | `logger.error(..., exc_info=True)` | `Unhandled exception in OCR Agent: ...` |

### Log Level Guidelines

| Level | When to use |
|---|---|
| `logger.info` | Normal progress, counts, field values |
| `logger.warning` | Recoverable edge cases (e.g., empty input, using fallback) |
| `logger.error` | Caught exceptions; always pass `exc_info=True` |
| `logger.debug` | Verbose internals useful during development only |

### Do Not

- Do not call `print()` anywhere in agent code.
- Do not log the full contents of large lists/dicts — log counts and previews only.
- Do not use `logging.basicConfig()` — the factory in `utils/logger.py` handles configuration.

---

## 7. Error Handling

Agents operate inside a shared pipeline. An unhandled exception that propagates up will terminate the entire run. Every agent must follow defensive error handling.

### Rules

1. **Wrap the entire body of your agent in a `try/except` block.**
2. **Catch `Exception` as the base type** — do not silently swallow errors with a bare `except:`.
3. **Log the exception** with `logger.error(..., exc_info=True)` so the traceback appears in logs.
4. **Append the error message** to `update["errors"]` using the format `"AgentName: <message>"`.
5. **Set safe defaults** for your owned output fields so downstream agents receive a valid (if empty) value.
6. **Return `update`** — the orchestrator must receive control back to route to an error handler or `END`.

### Pattern

```python
try:
    # ... agent logic ...
    update["my_field"] = result

except Exception as exc:
    logger.error(f"Unhandled exception in My Agent: {exc}", exc_info=True)
    update["errors"] = [f"MyAgent: {exc}"]
    update["my_field"] = <safe_default>   # e.g. [], None, 0.0

leave_node("My Agent", update, logger)
return update
```

### Do Not

- Do not `raise` inside an agent — it terminates the workflow.
- Do not catch-and-ignore: `except Exception: pass` — errors must be recorded.
- Do not reset or modify error messages added by previous agents. The `errors` list is an append-only audit trail.

---

## 8. Agent Template

Use this as your starting skeleton. Replace every placeholder with agent-specific logic. Do not deviate from the structure.

```python
"""
<AgentName> — ModifAI Pipeline.

Responsibilities
----------------
* <Single, clearly stated responsibility in one sentence.>

Routing consequence
-------------------
<Which node does the graph flow to after this agent?>

Note
----
<Stub vs. real implementation note. What external service/library will the real implementation use?>
"""

from graph.state import ModifAIState
from utils.logger import get_logger
from utils.node_helpers import build_base_update, enter_node, leave_node

logger = get_logger(__name__)


def <agent_name>_agent(state: ModifAIState) -> dict:
    """<One-line summary of this agent's purpose.>

    Args:
        state: The current shared pipeline state.

    Returns:
        A partial state dict containing only the fields updated by this agent.
    """
    enter_node("<Agent Display Name>", state, logger)
    update = build_base_update("<Agent Display Name>")

    try:
        # --- 1. Read required input fields ---
        input_value = state.get("<input_field>", <default>)
        logger.info(f"<Agent Display Name> received {len(input_value)} item(s).")

        # --- 2. Execute business logic ---
        result = _do_work(input_value)

        # --- 3. Write to owned output fields only ---
        update["<output_field>"] = result
        logger.info(f"  <output_field> set to {len(result)} item(s).")

    except Exception as exc:
        logger.error(
            f"Unhandled exception in <Agent Display Name>: {exc}", exc_info=True
        )
        update["errors"] = [f"<AgentClassName>: {exc}"]
        update["<output_field>"] = <safe_default>  # e.g. [], None, 0.0

    leave_node("<Agent Display Name>", update, logger)
    return update


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _do_work(input_value: list) -> list:
    """<One-line summary of what this helper does.>

    Args:
        input_value: <Description of parameter.>

    Returns:
        <Description of return value.>
    """
    # TODO: Replace stub with real implementation
    return []
```

---

## 9. Folder Structure

All agent files live directly under `agents/`. One file per agent. No subdirectories.

```
modifai/
├── agents/
│   ├── __init__.py
│   ├── validation.py       # Validation Agent
│   ├── ocr.py              # OCR Agent
│   ├── chunking.py         # Chunking Agent
│   ├── generation.py       # Dataset Generator Agent
│   ├── quality.py          # Quality Agent
│   ├── finetune.py         # Fine-Tuning Agent
│   ├── evaluation.py       # Evaluation Agent
│   └── deployment.py       # Deployment Agent
│
├── graph/                  # DO NOT MODIFY
│   ├── graph_builder.py
│   ├── routers.py
│   └── state.py
│
├── schemas/                # DO NOT MODIFY
│   └── state_schema.py
│
├── utils/                  # Read-only for agent developers
│   ├── logger.py
│   └── node_helpers.py
│
├── config/
└── tests/
    └── test_<agent_name>.py    # one test file per agent
```

- Agent file names must match the table above exactly — `graph_builder.py` registers nodes by importing these names.
- Each agent must have a corresponding test file in `tests/`.

---

## 10. State Ownership Table

This table is the definitive reference. An agent may **only** write to the fields listed in its **Updates** column.

| Agent | Reads | Updates |
|---|---|---|
| **Validation Agent** | `user_prompt`, `uploaded_files` | `validation_status`, `dataset_type`, `task_type`, `ocr_required` |
| **OCR Agent** | `uploaded_files` | `extracted_documents` |
| **Chunking Agent** | `extracted_documents`, `uploaded_files` (fallback) | `chunks` |
| **Dataset Generator** | `chunks`, `dataset_type`, `task_type` | `generated_dataset` |
| **Quality Agent** | `generated_dataset` | `dataset_quality_score` |
| **Fine-Tuning Agent** | `generated_dataset`, `task_type` | `training_job_id`, `training_status`, `model_uri` |
| **Evaluation Agent** | `model_uri`, `task_type` | `evaluation_metrics` |
| **Deployment Agent** | `model_uri`, `evaluation_metrics` | `deployment_url` |

**Orchestration fields managed automatically** — do not set these manually:

| Field | Managed by |
|---|---|
| `current_agent` | `build_base_update()` in `utils/node_helpers.py` |
| `execution_history` | `build_base_update()` + LangGraph `operator.add` reducer |
| `errors` | Each agent appends via `update["errors"] = [...]`; reducer handles accumulation |
| `session_id`, `user_prompt`, `uploaded_files`, `metadata` | Set by `ModifAIInputSchema.to_initial_state()` — never overwritten |

---

## 11. Integration Checklist

Before submitting your agent for code review, verify every item below. An agent that fails any check is not ready for integration.

- [ ] Agent reads **only** state fields it owns or is permitted to read.
- [ ] Agent returns **only** the partial state dict — never the full state object.
- [ ] Agent uses `build_base_update(...)` as the base for its return dict.
- [ ] Agent always returns `update`, including on the error path.
- [ ] Agent calls `enter_node(...)` at entry and `leave_node(...)` before return.
- [ ] Agent wraps its body in `try/except Exception`.
- [ ] Agent records errors in `update["errors"]` using the format `"AgentName: message"`.
- [ ] Agent sets safe defaults for its output fields in the error path.
- [ ] All functions have type hints and Google-style docstrings.
- [ ] Code passes `flake8` and `black --check`.
- [ ] A corresponding test file exists in `tests/test_<agent_name>.py`.
- [ ] Unit tests cover the happy path and at least one error path.
- [ ] Agent file contains no imports from another agent's module.
- [ ] No changes made to `graph/`, `schemas/`, or any other agent's file.

---

## 12. Definition of Done

An agent is **done** only when all of the following are true:

1. **Single responsibility** — the agent performs exactly one task, clearly stated in its module docstring.
2. **Contract compliance** — it follows the agent contract in full (correct signature, partial return, `build_base_update`, always returns `update`).
3. **Seamless integration** — it plugs into the existing LangGraph graph without any modification to `graph_builder.py`, `routers.py`, or `state.py`.
4. **Test coverage** — it has a test file that passes with `pytest`, covering at least the happy path and one failure path.
5. **State hygiene** — it updates only its designated fields and does not touch fields owned by other agents or the orchestration layer.
6. **Code quality** — it passes `flake8`, has type hints throughout, and all functions have Google-style docstrings.

---

*For questions about the orchestration backbone, graph topology, or routing logic, contact the orchestration lead. Do not attempt to resolve them by modifying shared infrastructure files.*
