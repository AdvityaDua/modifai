# ModifAI — Input Validation Module

**The intelligent checkpoint for AI pipelines.** This module runs *before* any dataset generation or agent fine-tuning begins. It acts as a strict data quality gate and intent classifier to ensure you never burn compute on garbage data.

---

## 🛑 The Problem

Most AI pipelines are blind optimists: they accept any document a user uploads and immediately start spending money (tokens and compute) to process it. 
If the user uploads a blurry 200-page scan, a completely corrupted file, or a recipe book when they asked for an HR assistant, the pipeline happily burns API credits only to produce a useless result.

## 🟢 Our Solution

**Spend money only when a free check genuinely cannot decide.**

ModifAI's Input Validation Module intercepts the document and answers two critical questions:
1. **Does this document match the user's stated intent?** (e.g., Is this document actually about HR policies if the user wants to build an HR chatbot?)
2. **Is the document readable and high enough quality to build from?** (e.g., Is it blurry, too sparse, or mostly unreadable?)

We use a layered, cost-minimizing architecture. Free, client-side local models handle the vast majority of the workload. Paid LLM calls are only used as a last resort for ambiguous cases and deep qualitative scoring.

---

## ✨ Key Features & Innovations

- **Multi-Format Document Support:** Processes both PDF files and plain text files (Markdown `.md`, Text `.txt`, CSV `.csv`).
- **Zero-Cost Instant Bypass:** Text-native documents (plain text, markdown, CSV) bypass heavy PDF loading and OCR pipelines entirely, cutting client-side load time and resources to 0.
- **Zero-Cost PDF Classification:** Uses Mozilla's `pdf.js` to instantly classify PDF pages as text-native, image-only (scanned), or mixed.
- **Wasm Client-Side OCR:** Performs OCR directly in the browser on scanned pages using `Tesseract.js` (WebAssembly), eliminating cloud-side OCR costs.
- **Local Semantic Embeddings:** Runs `Transformers.js` (`all-MiniLM-L6-v2`) inside the browser to match the document contents against the user's intent prompt without calling external APIs.
- **Smart Caching & Deduplication:**
  - **Jaccard Similarity Deduplication:** Removes duplicate/near-duplicate chunks before sending them to the LLM, reducing quality-check costs.
  - **OCR Caching:** Skips re-running expensive OCR if the user processes the same file with a refined intent prompt.
  - **Intent Caching:** Caches similarity metrics to bypass redundant model calls.
- **Interactive UX & Vagueness Warnings:** Warns users if their intent prompt is too generic (e.g., "AI assistant") and offers one-click AI-suggested refinements.
- **Premium, Responsive Interface:** Styled with a modern glassmorphism design, real-time logging stream, interactive feedback cards, and collapsible details for both mobile and desktop screens.

---

## 🏗️ Technical Architecture & Pipeline

The module runs an optimized 7-stage validation pipeline:

| Stage | Action | Execution | Cost |
|---|---|---|---|
| **1. Classification** | Scans file. Detects if it's text/markdown (bypasses to chunking) or a PDF. Classifies PDF pages. | Local (`pdf.js` or plain text reader) | **Free** |
| **2. Selective OCR** | Runs Tesseract OCR only on image-only/scanned PDF pages. | Local (`Tesseract.js` Wasm) | **Free** |
| **3. Semantic Chunking** | Splits text on natural boundaries and extracts a stratified sample. | Local (JS logic) | **Free** |
| **4. Intent Matching** | Compares text embeddings against user intent to verify topic alignment. | Local (`Transformers.js`) | **Free** |
| **5. LLM Escalation** | If local similarity is ambiguous (0.4 to 0.7), an LLM resolves the verdict. | API (`OpenRouter`) | ~$0.001 |
| **6. Quality Scoring** | LLM rates sampled chunks on specificity, grounding, and readability. | API (`OpenRouter`) | ~$0.001 / chunk |
| **7. Aggregation** | Computes a final score to `proceed` (auto-hand-off), `block` (reject), or `confirm` (ask user). | Local (JS logic) | **Free** |

---

## 📂 Project Structure

Here is a guide to the key files in the repository:

```
├── server.js               # Express server that injects API keys securely and serves static assets
├── index.html              # Main frontend app containing the pipeline UI and Web Orchestrator
├── render.yaml             # Render deployment configuration
├── package.json            # Project dependencies and script definitions
└── src/
    ├── types.ts            # TypeScript definitions for pipeline results, settings, and cache
    ├── pdfGuard.ts         # Preflight security guard (file size, page limit checking)
    ├── pdfLoader.ts        # PDF parsing and page classification module
    ├── ocrProcessor.ts     # Client-side Tesseract OCR wrapper
    ├── chunker.ts          # Text chunking, cleanup, and Jaccard deduplication logic
    ├── intentClassifier.ts # Local embeddings classifier and OpenRouter intent verification
    ├── qualityValidator.ts # OpenRouter chunk quality scoring logic
    ├── aggregator.ts       # Confidence scoring and pipeline decision logic
    ├── sessionCache.ts     # OCR and intent caching management
    ├── orchestrator.ts     # Master Node orchestrator
    └── browser/
        └── browserOrchestrator.ts # Browser pipeline runner translating node logic to browser runtime
```

---

## 🚀 Running Locally

### Prerequisites
- Node.js (v18 or higher)
- An OpenRouter API Key (to run the optional LLM checks)

### Step-by-Step Setup

1. **Clone the repository and install dependencies:**
   ```bash
   git clone https://github.com/AdvityaDua/modifai.git
   cd modifai
   npm install
   ```

2. **Configure Environment Variables:**
   Create a `.env` file in the root directory:
   ```env
   OPENROUTER_API_KEY=your-openrouter-api-key-here
   PORT=3000
   ```

3. **Start the local server:**
   ```bash
   npm start
   ```

4. **Access the application:**
   Open [http://localhost:3000](http://localhost:3000) in your web browser.

---

## ☁️ Deploying to Render

This repository includes a `render.yaml` file for instant deployment to [Render](https://render.com).

1. Log in to your Render dashboard.
2. Click **New** -> **Blueprint**.
3. Connect your GitHub repository.
4. Render will automatically read `render.yaml` and configure the Node.js service.
5. Add your `OPENROUTER_API_KEY` under the service's Environment variables. **Never commit your API key to the repository.**

---

## 🔌 API Integration & Output Handoff

Once validation finishes with a `proceed` or `confirm` decision, a structured JSON object is generated. The next step in the ModifAI pipeline (e.g. Dataset Generator) can retrieve this validated output directly:

```json
{
  "finalScore": 92.5,
  "intentVerdict": "match",
  "intentSimilarity": 0.812,
  "decision": "proceed",
  "reason": "Document quality and intent match both look good.",
  "headline": "Document looks great - ready to proceed",
  "nextSteps": [
    {
      "priority": "medium",
      "icon": "Check",
      "action": "Your document is ready. 12 chunk(s) will be passed to the ModifAI dataset generator."
    }
  ],
  "pageBreakdown": {
    "total": 5,
    "textNative": 5,
    "imageOnly": 0,
    "mixed": 0
  },
  "sampledChunks": 8,
  "scoredChunks": [
    {
      "chunkId": "p1-c0",
      "qualityScore": 95,
      "extractionConfidence": 1.0,
      "issues": []
    }
  ],
  "timings": {
    "pdfLoad": 120,
    "ocr": 0,
    "chunking": 15,
    "intentCheck": 250,
    "qualityScoring": 1200,
    "total": 1585
  },
  "allIssues": []
}
```

This ensures that downstream pipelines receive only high-quality, relevant data, preventing unnecessary computational overhead and API costs.
