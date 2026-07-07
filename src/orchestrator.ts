/**
 * src/orchestrator.ts — Module G
 * Main Orchestration Entry Point (Node.js / Server-side)
 *
 * Ties all modules together for the server-side / Node.js usage path.
 * For browser-based usage (with canvas rendering for OCR), use browserOrchestrator.ts.
 *
 * Pipeline:
 *  1. Load PDF + classify pages (Module A)
 *  2. OCR flagged pages (Module B — canvas rendering omitted in Node; see note)
 *  3. Chunk everything with source tags (Module C)
 *  4. Stratified sample (Module C)
 *  5. Intent check: embeddings → LLM only if ambiguous (Module D)
 *  6. Quality scoring on sampled chunks (Module E)
 *  7. Aggregate + decide (Module F)
 */

import { loadAndClassifyPdf } from "./pdfLoader";
import { buildAllChunks, stratifiedSample } from "./chunker";
import { checkIntentMatch, llmIntentVerdict, similarityToVerdict } from "./intentClassifier";
import { scoreAllChunks } from "./qualityValidator";
import { aggregateScore, decide } from "./aggregator";
import type { ValidationResult, IntentVerdict, ProgressEvent, PipelineStage } from "./types";

export type { ValidationResult };

/**
 * Run the full input validation pipeline.
 *
 * @param fileBuffer - Raw PDF bytes
 * @param userIntent - The user's stated intent (e.g. "I want an HR policy assistant")
 * @param apiKey - OpenRouter API key (required for LLM calls; free path works without it for clear cases)
 * @param onProgress - Optional callback for real-time progress updates
 */
export async function validateUpload(
  fileBuffer: Uint8Array,
  userIntent: string,
  apiKey: string,
  onProgress?: (event: ProgressEvent) => void
): Promise<ValidationResult> {
  const emit = (stage: PipelineStage, message: string, progress?: number, detail?: string) => {
    if (onProgress) onProgress({ stage, message, progress, detail });
  };

  const totalStart = performance.now();
  const timings = { pdfLoad: 0, ocr: 0, chunking: 0, intentCheck: 0, qualityScoring: 0, total: 0 };

  // ── Step 1: Load PDF & classify pages ──────────────────────────────────────
  emit("pdf-loading", "Loading and classifying PDF pages…", 0);
  const t0 = performance.now();

  const pages = await loadAndClassifyPdf(fileBuffer, (pageNum, total) => {
    emit("page-classification", `Classifying page ${pageNum} of ${total}…`, Math.round((pageNum / total) * 30));
  });

  timings.pdfLoad = performance.now() - t0;

  const textNative = pages.filter((p) => p.classification === "text-native").length;
  const imageOnly = pages.filter((p) => p.classification === "image-only").length;
  const mixed = pages.filter((p) => p.classification === "mixed").length;
  const ocrNeeded = pages.filter((p) => p.needsOCR).length;

  emit(
    "page-classification",
    `Page classification complete: ${textNative} text-native, ${imageOnly} image-only, ${mixed} mixed.`,
    30,
    `${ocrNeeded} page(s) need OCR.`
  );

  // ── Step 2: OCR (Node.js note) ──────────────────────────────────────────────
  // In Node.js, canvas rendering for PDF pages requires additional native deps (canvas package).
  // For this module, OCR in Node is skipped with a clear log — use the browser orchestrator
  // (src/browser/browserOrchestrator.ts) for full OCR support.
  const t1 = performance.now();

  if (ocrNeeded > 0) {
    emit(
      "ocr",
      `${ocrNeeded} page(s) need OCR. In Node.js mode, OCR is deferred to the browser layer.`,
      35,
      "Use the browser demo for full OCR support."
    );
    console.warn(
      `[orchestrator] ${ocrNeeded} pages need OCR but canvas rendering is not available in Node.js mode. ` +
        "Text from those pages will not be OCR'd. Use index.html for full browser-based OCR."
    );
  }

  timings.ocr = performance.now() - t1;

  // ── Step 3: Chunking ────────────────────────────────────────────────────────
  emit("chunking", "Chunking extracted text…", 40);
  const t2 = performance.now();

  const allChunks = buildAllChunks(
    pages.map((p) => ({
      pageNumber: p.pageNumber,
      extractedText: p.extractedText,
      needsOCR: p.needsOCR,
      ocrResult: undefined, // Node.js mode — no OCR results
    }))
  );

  timings.chunking = performance.now() - t2;

  if (allChunks.length === 0) {
    return {
      finalScore: 0,
      intentVerdict: "mismatch",
      intentSimilarity: 0,
      decision: "block",
      reason:
        "No extractable text found in the document. The PDF may be entirely image-based. " +
        "Please use the browser demo for OCR support, or upload a text-native PDF.",
      pageBreakdown: { total: pages.length, textNative, imageOnly, mixed },
      sampledChunks: 0,
      scoredChunks: [],
      timings: { ...timings, total: performance.now() - totalStart },
    };
  }

  // ── Step 4: Stratified sampling ─────────────────────────────────────────────
  emit("sampling", `Sampling from ${allChunks.length} chunks…`, 45);
  const sample = stratifiedSample(allChunks);
  const combinedSampleText = sample.map((c) => c.text).join("\n\n");

  emit("sampling", `Selected ${sample.length} chunks for validation.`, 50);

  // ── Step 5: Intent check ────────────────────────────────────────────────────
  emit("intent-check", "Running intent check (local embeddings)…", 55);
  const t3 = performance.now();

  const { similarity, needsLLMCheck } = await checkIntentMatch(userIntent, combinedSampleText);
  let intentVerdict: IntentVerdict = similarityToVerdict(similarity);
  let intentReason = "";

  if (needsLLMCheck && apiKey) {
    emit("intent-check", "Similarity in ambiguous range — escalating to LLM for verdict…", 60);
    try {
      const llmResult = await llmIntentVerdict(userIntent, combinedSampleText, apiKey);
      intentVerdict = llmResult.verdict;
      intentReason = llmResult.reason;
    } catch (err) {
      console.warn("[orchestrator] LLM intent check failed, falling back to embedding verdict:", err);
    }
  } else if (needsLLMCheck && !apiKey) {
    console.warn("[orchestrator] Similarity is borderline but no API key provided; using embedding verdict.");
  }

  timings.intentCheck = performance.now() - t3;

  emit(
    "intent-check",
    `Intent verdict: ${intentVerdict} (similarity: ${similarity.toFixed(3)})`,
    65,
    intentReason
  );

  // ── Step 6: Quality scoring ─────────────────────────────────────────────────
  emit("quality-scoring", `Scoring ${sample.length} sampled chunks for quality…`, 70);
  const t4 = performance.now();

  let scoredChunks: Array<{
    chunkId: string;
    qualityScore: number;
    extractionConfidence: number;
    issues: string[];
  }> = [];

  if (apiKey) {
    scoredChunks = await scoreAllChunks(
      sample.map((c) => ({ id: c.id, text: c.text, confidence: c.confidence })),
      apiKey,
      (done, total, score) => {
        emit("quality-scoring", `Scored chunk ${done}/${total} (score: ${score})`, 70 + Math.round((done / total) * 20));
      }
    );
  } else {
    // No API key — estimate quality from OCR confidence + text length heuristics
    console.warn("[orchestrator] No API key — estimating quality from heuristics.");
    scoredChunks = sample.map((c) => ({
      chunkId: c.id,
      qualityScore: Math.round(c.confidence * 80 + (Math.min(c.text.length, 500) / 500) * 20),
      extractionConfidence: c.confidence,
      issues: c.confidence < 0.7 ? ["Low OCR confidence"] : [],
    }));
  }

  timings.qualityScoring = performance.now() - t4;

  // ── Step 7: Aggregate + decide ──────────────────────────────────────────────
  emit("aggregation", "Aggregating scores and computing final decision…", 92);

  const finalScore = aggregateScore(scoredChunks);
  const decisionResult = decide(finalScore, intentVerdict);

  timings.total = performance.now() - totalStart;

  emit(
    "done",
    `Validation complete. Score: ${finalScore.toFixed(1)}/100. Decision: ${decisionResult.decision}.`,
    100
  );

  return {
    finalScore,
    intentVerdict,
    intentSimilarity: similarity,
    decision: decisionResult.decision,
    reason: decisionResult.reason,
    pageBreakdown: { total: pages.length, textNative, imageOnly, mixed },
    sampledChunks: sample.length,
    scoredChunks,
    timings,
  };
}
