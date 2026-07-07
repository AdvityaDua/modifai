# ModifAI — Step 1: Input Validation Module

> **Intent Classification Agent + Data Quality Gate**
> The first intelligent checkpoint in the ModifAI pipeline — runs before a single dollar of compute is spent on dataset generation, agent discovery, or fine-tuning.

---

## The Problem We're Solving

When a user uploads a PDF and says *"build me an HR policy assistant"*, two silent failures can happen before any real AI work begins:

1. **Wrong document.** The PDF is actually a sales contract. The entire downstream pipeline produces garbage.
2. **Bad document.** The PDF is a 200-page blurry scan. Even if it's the right kind, the output quality will be terrible.

Traditional approaches either ignore this and proceed (wasting credits), or run expensive cloud OCR on every page of every document (wasting money). **ModifAI does neither.**

---

## The Architecture: Zero Server Cost by Design

```
User's Browser
  ├── pdf.js          → Free text extraction, no upload needed
  ├── Tesseract.js    → Free OCR via WebAssembly (runs on user's device, not our server)
  └── Transformers.js → Free semantic embeddings (MiniLM, runs locally in-browser)
       │
       └─ Only if similarity is ambiguous (0.4–0.7 band):
            └── OpenRouter LLM → 1 cheap API call for definitive verdict

Server (Express)
  └── Injects API key from environment → serves static HTML
```

**The guiding principle: spend money only when a free check genuinely cannot decide.**

---

## Pipeline — 7 Stages

| Stage | What Happens | Cost |
|---|---|---|
| **A — PDF Classification** | Every page classified as text-native, image-only, or mixed using pdf.js | Free |
| **B — Selective OCR** | *Only* image-flagged pages rendered to canvas and processed by Tesseract.js WASM | Free (client CPU) |
| **C — Semantic Chunking** | Text split on paragraph boundaries with √-scaled stratified sampling | Free |
| **D — Intent Matching** | `all-MiniLM-L6-v2` embeds user intent vs. document sample; cosine similarity computed | Free |
| **D — LLM Escalation** | If similarity is 0.4–0.7 (genuinely ambiguous), one LLM call gets a verdict | ~$0.001 |
| **E — Quality Scoring** | LLM rates sampled chunks on specificity, grounding, and readability | ~$0.001/chunk |
| **F — Aggregation** | Confidence-weighted mean score → `proceed` / `confirm-with-user` / `block` | Free |

---

## Tech Stack Decisions

| Tool | Purpose | Why specifically this |
|---|---|---|
| **pdf.js** (Mozilla) | PDF parsing + text-layer detection | Runs in the browser; no upload to a third-party server; detects text-native pages so OCR is never run unnecessarily |
| **Tesseract.js** (WASM) | OCR for scanned pages | Zero server cost — compute runs on the user's device. Cloud OCR (AWS Textract, Google DocAI) charges per page; this charges nothing |
| **`all-MiniLM-L6-v2`** via Transformers.js | Intent-document similarity | 384-dimensional embeddings that run fully in-browser. No API key, no latency, no cost for the majority of documents that are clearly matching or clearly not |
| **OpenRouter** (`llama-3.1-8b`, `qwen-2.5-7b`) | LLM verdict + quality scoring | Aggregator access to cheap open-weight models. Only called for the genuinely ambiguous cases (~20–30% of uploads) |
| **Express** | Serving the static app | Injects the API key from the server environment — the key is never in client code, never in the git history |

---

## Running Locally

```bash
# 1. Clone & install
git clone https://github.com/AdvityaDua/modifai.git
cd modifai
npm install

# 2. Add your OpenRouter API key
cp .env.example .env
# Open .env and set: OPENROUTER_API_KEY=sk-or-...

# 3. Start
npm start
# → http://localhost:3000
```

### Using the App
1. Drop a PDF into the upload zone
2. Type your intent (e.g. *"I want to build an HR policy assistant"*)
3. Click **Run Validation**
4. Watch the 7-stage pipeline run in real time — the final result tells you exactly why the document passed, needs confirmation, or was blocked

---

## Deploying to Render

1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repo and select this folder
3. Render auto-detects `render.yaml` and configures the service
4. In the Render dashboard → **Environment** → add `OPENROUTER_API_KEY`
5. Deploy — that's it

The `render.yaml` in this repo handles everything else.

---

## Acceptance Checklist (from Build Manual §13)

- [ ] Text-native PDF → zero OCR calls, processed in milliseconds
- [ ] Scanned PDF (matching intent) → OCR runs, confidence scores visible in results
- [ ] Scanned PDF (poor quality) → blocked with specific reason
- [ ] Mixed PDF → only the scanned page goes through Tesseract
- [ ] Wrong-intent PDF → blocked for intent mismatch, not quality
- [ ] Borderline case → "Proceed anyway?" confirmation shown to user
- [ ] LLM spend: handful of calls per document, never one per chunk

---

## Project Structure

```
step1-input-validation/
  server.js                       ← Express server (injects API key, serves static files)
  index.html                      ← Browser demo UI (drag-and-drop, real-time pipeline)
  render.yaml                     ← One-click Render deployment config
  src/
    types.ts                      ← Shared TypeScript interfaces for all modules
    pdfLoader.ts                  ← Module A: PDF loading + page classification
    ocrProcessor.ts               ← Module B: Tesseract.js OCR + image preprocessing
    chunker.ts                    ← Module C: Semantic chunking + stratified sampling
    intentClassifier.ts           ← Module D: MiniLM embeddings + LLM escalation
    qualityValidator.ts           ← Module E: LLM quality scoring
    aggregator.ts                 ← Module F: Confidence-weighted aggregation + decision
    orchestrator.ts               ← Module G: Node.js entry point
    browser/
      browserOrchestrator.ts      ← Browser-specific pipeline (with canvas OCR)
    test/
      runValidation.ts            ← CLI test runner
```

---

## What This Hands Off

When `validateUpload()` returns `decision: "proceed"` (or the user confirms on a borderline case), the resulting chunks — already tagged with `source_type` and `confidence` — are passed directly to the LangChain/LangGraph orchestrator in Step 2. This module's job ends here. It is a gate, not a generator.

---

*Built for the ModifAI hackathon · Step 1 of the pipeline*
