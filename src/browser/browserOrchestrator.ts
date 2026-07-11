/**
 * src/browser/browserOrchestrator.ts — Browser Orchestrator
 *
 * Browser-specific version of the validation pipeline that handles canvas rendering
 * for OCR (which can't be done server-side without native deps).
 *
 * This is what the index.html demo UI calls.
 *
 * Pipeline (same as orchestrator.ts but with full OCR support):
 *  1. Load PDF + classify pages
 *  2. Render OCR-flagged pages to canvas → preprocess → Tesseract.js
 *  3. Chunk everything
 *  4. Stratified sample
 *  5. Intent check (embeddings → LLM if ambiguous)
 *  6. Quality scoring
 *  7. Aggregate + decide
 */

import { loadAndClassifyPdf, renderPageToCanvas, detectDocumentType } from "../pdfLoader";
import { preprocessCanvas, runOcrOnPage } from "../ocrProcessor";
import { buildAllChunks, stratifiedSample } from "../chunker";
import { checkIntentMatch, llmIntentVerdict, similarityToVerdict, checkIntentVagueness, expandIntent } from "../intentClassifier";
import { scoreAllChunks } from "../qualityValidator";
import { aggregateScore, decide, buildSummary } from "../aggregator";
import { pdfPreflight } from "../pdfGuard";
import { detectLanguage } from "../languageDetector";
import type { ValidationResult, IntentVerdict, ProgressEvent, PipelineStage, OcrResult, PreflightResult, ExpandedIntent, DocumentType } from "../types";

export type { ValidationResult };

export interface BrowserValidationResult extends ValidationResult {
  summary: ReturnType<typeof buildSummary>;
  allIssues: string[];
}

/**
 * Run the full browser-based validation pipeline with OCR support.
 */
export async function browserValidateUpload(
  file: File,
  userIntent: string,
  apiKey: string,
  onProgress?: (event: ProgressEvent) => void
): Promise<BrowserValidationResult> {
  const emit = (stage: PipelineStage, message: string, progress?: number, detail?: string) => {
    if (onProgress) onProgress({ stage, message, progress, detail });
    console.log(`[${stage}] ${message}`, detail ?? "");
  };

  const totalStart = performance.now();
  const timings = { pdfLoad: 0, ocr: 0, chunking: 0, intentCheck: 0, qualityScoring: 0, total: 0 };

  // Convert File → Uint8Array
  const arrayBuffer = await file.arrayBuffer();
  const fileBuffer = new Uint8Array(arrayBuffer);

  // ── Phase 1.1: Pre-flight validation ──────────────────────────────────────
  emit("pdf-loading", "Checking file…", 2);
  const preflight = await pdfPreflight(file);
  if (!preflight.ok) {
    // Return early with a structured error — no pipeline stages run
    throw Object.assign(new Error(preflight.reason), {
      actionableHint: preflight.actionableHint,
      isPreflight: true,
    });
  }

  // ── Step 1: Load PDF & classify pages ──────────────────────────────────────
  emit("pdf-loading", "Loading PDF…", 5);
  const t0 = performance.now();

  const pages = await loadAndClassifyPdf(fileBuffer, (pageNum, total) => {
    emit("page-classification", `Classifying page ${pageNum}/${total}…`, 5 + Math.round((pageNum / total) * 20));
  });

  timings.pdfLoad = performance.now() - t0;

  const textNative = pages.filter((p) => p.classification === "text-native").length;
  const imageOnly = pages.filter((p) => p.classification === "image-only").length;
  const mixed = pages.filter((p) => p.classification === "mixed").length;
  const ocrPages = pages.filter((p) => p.needsOCR);

  emit("page-classification", `${textNative} text-native | ${imageOnly} image-only | ${mixed} mixed`, 25);

  // ── Phase 1.2: Language detection ─────────────────────────────────────
  // Sample text from first 3 text-native pages (no cost, already extracted)
  const langSample = pages
    .filter((p) => !p.needsOCR && p.extractedText.length > 20)
    .slice(0, 3)
    .map((p) => p.extractedText)
    .join(" ")
    .slice(0, 500);
  const langResult = detectLanguage(langSample);
  if (langResult.confident && langResult.tesseractLang !== "eng") {
    emit("page-classification", `Detected language: ${langResult.displayName} — OCR will use ${langResult.tesseractLang} mode.`, 26);
  } else if (!langResult.confident && ocrPages.length > 0) {
    emit("page-classification", "Language unclear — defaulting to English OCR. If results look wrong, the document may be in another language.", 26);
  }

  // ── Phase 2.3: Document type detection ────────────────────────────────
  const allExtractedText = pages.map((p) => p.extractedText).join(" ");
  const docType: DocumentType = detectDocumentType(allExtractedText);
  if (docType !== "prose") {
    emit("page-classification", `Document type detected: ${docType} — quality rubric adjusted.`, 27);
  }

  // ── Step 2: OCR flagged pages ───────────────────────────────────────────────
  const t1 = performance.now();
  const ocrResults = new Map<number, OcrResult>();

  if (ocrPages.length > 0) {
    emit("ocr", `Running OCR on ${ocrPages.length} page(s)…`, 28);

    for (let i = 0; i < ocrPages.length; i++) {
      const ocrPage = ocrPages[i];
      const progress = 28 + Math.round(((i + 0.5) / ocrPages.length) * 22);

      emit("ocr", `OCR page ${ocrPage.pageNumber} (${i + 1}/${ocrPages.length})…`, progress);

      try {
        // Render the page to canvas at 2x scale for better OCR accuracy
        const canvas = await renderPageToCanvas(fileBuffer, ocrPage.pageNumber, 2.0);

        // Preprocess: grayscale + binarization
        preprocessCanvas(canvas);

        // Run Tesseract with detected language
        const ocrResult = await runOcrOnPage(canvas, ocrPage.pageNumber, undefined, langResult.tesseractLang);
        ocrResults.set(ocrPage.pageNumber, ocrResult);

        emit(
          "ocr",
          `Page ${ocrPage.pageNumber} OCR done (confidence: ${ocrResult.averageConfidence.toFixed(1)}%)`,
          28 + Math.round(((i + 1) / ocrPages.length) * 22)
        );
      } catch (err) {
        console.warn(`[OCR] Failed on page ${ocrPage.pageNumber}:`, err);
        emit("ocr", `OCR failed on page ${ocrPage.pageNumber} — skipping.`, progress, String(err));
      }
    }
  }

  timings.ocr = performance.now() - t1;

  // ── Step 3: Chunking ────────────────────────────────────────────────────────
  emit("chunking", "Chunking document text…", 52);
  const t2 = performance.now();

  const allChunks = buildAllChunks(
    pages.map((p) => ({
      pageNumber: p.pageNumber,
      extractedText: p.extractedText,
      needsOCR: p.needsOCR,
      ocrResult: ocrResults.get(p.pageNumber)
        ? {
            text: ocrResults.get(p.pageNumber)!.text,
            averageConfidence: ocrResults.get(p.pageNumber)!.averageConfidence,
          }
        : undefined,
    }))
  );

  timings.chunking = performance.now() - t2;

  if (allChunks.length === 0) {
    const emptyResult: BrowserValidationResult = {
      finalScore: 0,
      intentVerdict: "mismatch",
      intentSimilarity: 0,
      decision: "block",
      reason:
        "No extractable text found. The PDF may be entirely image-based and OCR may have failed. " +
        "Try a higher-resolution scan.",
      pageBreakdown: { total: pages.length, textNative, imageOnly, mixed },
      sampledChunks: 0,
      scoredChunks: [],
      timings: { ...timings, total: performance.now() - totalStart },
      summary: { qualityGrade: "F", intentGrade: "Mismatch", averageOcrConfidence: null, lowConfidenceChunks: 0 },
      allIssues: ["No extractable text found in document."],
    };
    emit("done", "Validation complete — no text found.", 100);
    return emptyResult;
  }

  // ── Step 4a: Intent expansion (before sampling — keywords drive chunk selection) ──
  // Phase 2.1: Vagueness check (free, deterministic — no LLM)
  const vagueness = checkIntentVagueness(userIntent);
  if (vagueness.vague) {
    emit("intent-check", `Intent may be too vague (${vagueness.reason}). Suggestion: ${vagueness.suggestion}`, 54);
  }

  // Phase 2.2: Intent expansion (one LLM call — keywords feed Phase 3.2 sampling)
  let expandedIntent: ExpandedIntent | null = null;
  let queryForEmbedding = userIntent;
  if (apiKey) {
    emit("intent-check", "Expanding intent for better matching…", 55);
    expandedIntent = await expandIntent(userIntent, apiKey);
    if (expandedIntent) {
      queryForEmbedding = expandedIntent.refined_query;
      emit("intent-check",
        `Intent understood — Domain: ${expandedIntent.domain} | Use case: ${expandedIntent.use_case}`,
        56, `Keywords: ${expandedIntent.document_keywords.join(", ")}`
      );
    }
  }

  // ── Step 4b: Stratified sampling (keyword-weighted when expansion succeeded) ──
  const keywords = expandedIntent?.document_keywords ?? [];
  emit("sampling", `${allChunks.length} chunks created. Selecting sample…`, 57);
  const sample = stratifiedSample(allChunks, keywords);  // Phase 3.2: relevance-weighted
  const combinedSampleText = sample.map((c) => c.text).join("\n\n");

  if (keywords.length > 0) {
    emit("sampling", `Selected ${sample.length} chunks (keyword-weighted + positional).`, 59);
  } else {
    emit("sampling", `Selected ${sample.length} chunks for validation.`, 59);
  }

  // ── Step 5: Intent match check (local embeddings) ─────────────────────────
  emit("intent-check", "Checking intent match (local embeddings)…", 63);
  const t3 = performance.now();

  const { similarity, needsLLMCheck } = await checkIntentMatch(queryForEmbedding, combinedSampleText);
  let intentVerdict: IntentVerdict = similarityToVerdict(similarity);
  let intentReason = "";

  if (needsLLMCheck && apiKey) {
    emit("intent-check", `Similarity ${similarity.toFixed(3)} is borderline — asking LLM…`, 66);
    try {
      const llmResult = await llmIntentVerdict(userIntent, combinedSampleText, apiKey);
      intentVerdict = llmResult.verdict;
      intentReason = llmResult.reason;
    } catch (err) {
      console.warn("[browserOrchestrator] LLM intent check failed:", err);
    }
  }

  timings.intentCheck = performance.now() - t3;
  emit("intent-check", `Intent: ${intentVerdict} (score: ${similarity.toFixed(3)})`, 70, intentReason);


  // ── Step 6: Quality scoring ─────────────────────────────────────────────────
  emit("quality-scoring", `Scoring ${sample.length} chunks for quality…`, 72);
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
        emit("quality-scoring", `Scored ${done}/${total} (score: ${score})`, 72 + Math.round((done / total) * 18));
      },
      docType  // Phase 2.3: adjusted rubric based on document type
    );
  } else {
    // Heuristic scoring — no LLM
    scoredChunks = sample.map((c) => ({
      chunkId: c.id,
      qualityScore: Math.round(c.confidence * 75 + (Math.min(c.text.length, 500) / 500) * 25),
      extractionConfidence: c.confidence,
      issues: c.confidence < 0.7 ? ["Low OCR confidence detected"] : [],
    }));
    emit("quality-scoring", "No API key — using heuristic quality scores.", 90);
  }

  timings.qualityScoring = performance.now() - t4;

  // ── Step 7: Aggregate + decide ──────────────────────────────────────────────
  emit("aggregation", "Computing final score and decision…", 94);

  const finalScore = aggregateScore(scoredChunks);
  const decisionResult = decide(finalScore, intentVerdict);
  const summary = buildSummary(finalScore, intentVerdict, similarity, scoredChunks);

  // Collect all unique issues for display
  const allIssues = [
    ...new Set(scoredChunks.flatMap((c) => c.issues).filter((i) => i.trim().length > 0)),
  ];

  timings.total = performance.now() - totalStart;

  emit("done", `Done! Score: ${finalScore.toFixed(1)}/100 | Decision: ${decisionResult.decision}`, 100);

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
    summary,
    allIssues,
  };
}
