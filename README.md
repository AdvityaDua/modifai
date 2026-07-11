# ModifAI — Input Validation Module

**The intelligent checkpoint for AI pipelines.** This module runs *before* any dataset generation or agent fine-tuning begins. It acts as a strict data quality gate and intent classifier to ensure you never burn compute on garbage data.

---

## 🛑 The Problem

Most AI pipelines are blind optimists: they accept any document a user uploads and immediately start spending money (tokens and compute) to process it. 
If the user uploads a blurry 200-page scan, or a recipe book when they asked for an HR assistant, the pipeline happily burns API credits only to produce a useless result.

## 🟢 Our Solution

**Spend money only when a free check genuinely cannot decide.**
ModifAI's Input Validation Module intercepts the document and answers two critical questions:
1. **Does this document match the user's stated intent?** 
2. **Is the document readable and high enough quality to build from?**

We use a layered, cost-minimizing architecture. Free, client-side local models handle the vast majority of the workload. Paid LLM calls are only used as a last resort for ambiguous cases and deep qualitative scoring.

---

## ✨ Key Features & Innovations

- **Zero-Cost PDF Parsing:** Uses Mozilla's `pdf.js` to detect text-native vs. image-only pages instantly in the browser.
- **Client-Side OCR:** Uses `Tesseract.js` (WebAssembly) to OCR scanned pages directly on the user's device. Eliminates expensive cloud OCR costs (like AWS Textract).
- **Local Semantic Embeddings:** Uses `Transformers.js` (`all-MiniLM-L6-v2`) entirely in the browser to check document relevance against the user's intent.
- **Smart Caching & Deduplication:** 
  - **Jaccard Similarity Deduplication:** Prevents near-duplicate text chunks from being sent to the LLM, saving API costs and time.
  - **OCR Caching:** If a user re-runs the same document with a refined intent, expensive OCR steps are automatically skipped.
  - **Intent Caching:** Identical intent prompts hit a fast in-session cache to bypass redundant LLM expansion calls.
- **Interactive UX:** Vagueness detection warns users if their prompt is too generic and offers one-click, AI-generated suggestions to improve it. The UI is fully responsive, featuring collapsible data tables for mobile devices.

---

## 🏗️ Technical Architecture

The module operates in a highly optimized 7-stage pipeline:

| Stage | Action | Execution | Cost |
|---|---|---|---|
| **1. PDF Classification** | Scans pages to identify text-native vs. image-only pages. | Local (`pdf.js`) | **Free** |
| **2. Selective OCR** | Runs OCR *only* on image-heavy pages. | Local (`Tesseract.js`) | **Free** |
| **3. Semantic Chunking** | Splits text on natural paragraph boundaries and performs stratified sampling. | Local (JS logic) | **Free** |
| **4. Intent Matching** | Compares chunk embeddings against user intent to ensure topic alignment. | Local (`Transformers.js`) | **Free** |
| **5. LLM Escalation** | If local similarity is ambiguous (0.4–0.7), an LLM makes the final call. | API (`OpenRouter`) | ~$0.001 |
| **6. Quality Scoring** | LLM rates sampled chunks on specificity, grounding, and readability. | API (`OpenRouter`) | ~$0.001 / chunk |
| **7. Aggregation** | Computes a confidence-weighted score to `proceed`, `block`, or `confirm`. | Local (JS logic) | **Free** |

---

## 🚀 Running Locally

### Prerequisites
- Node.js (v18+)
- An OpenRouter API Key (for the fallback LLM checks)

### Setup
```bash
# 1. Clone & install dependencies
git clone https://github.com/AdvityaDua/modifai.git
cd modifai
npm install

# 2. Configure Environment
cp .env.example .env
# Edit .env and add your key: OPENROUTER_API_KEY=sk-or-...

# 3. Start the application
npm start
```

### Usage
1. Open `http://localhost:3000` in your browser.
2. Drag and drop a PDF into the upload zone.
3. Type your intent (e.g., *"I want an assistant to answer employee HR questions"*). If your intent is too vague, the UI will warn you and provide a better suggestion!
4. Click **Run Validation**.
5. Watch the real-time pipeline execute and view the final chunk scores, extracted issues, and overall verdict.

---

## 🛡️ Security & Privacy

- **No API Keys in the Browser:** The Express server securely injects the API key at runtime. It is never exposed in the static HTML files or committed to the GitHub repository.
- **Local-First Processing:** Documents are processed heavily on the client side, ensuring maximum privacy before any chunks are ever sent to an external LLM.

---

## 🤝 Next Steps / Handoff

When a document passes validation (decision: `proceed`), the parsed, scored, and source-tagged chunks are ready to be passed directly to the **ModifAI Dataset Generator** (Step 2 of the pipeline) with absolute confidence in the data quality and intent match.

---
*Built for the ModifAI Hackathon*
