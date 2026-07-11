/**
 * src/types.ts
 * Shared TypeScript types and interfaces for the ModifAI Input Validation Module.
 */

// ─── Module A: PDF Loading ──────────────────────────────────────────────────

export type PageClassification = "text-native" | "image-only" | "mixed";

export interface PageResult {
  pageNumber: number;
  classification: PageClassification;
  extractedText: string;
  needsOCR: boolean;
}

// ─── Module B: OCR ─────────────────────────────────────────────────────────

export interface OcrResult {
  pageNumber: number;
  text: string;
  /** 0–100, straight from Tesseract */
  averageConfidence: number;
  wordConfidences: { word: string; confidence: number }[];
}

// ─── Module C: Chunking ─────────────────────────────────────────────────────

export interface Chunk {
  id: string;
  text: string;
  sourceType: "text-native" | "ocr";
  /** 1.0 for text-native; Tesseract averageConfidence / 100 for OCR */
  confidence: number;
  pageNumber: number;
}

// ─── Module D: Intent Classification ───────────────────────────────────────

export type IntentVerdict = "match" | "partial" | "mismatch";

export interface IntentCheckResult {
  similarity: number;
  needsLLMCheck: boolean;
}

export interface LLMIntentResult {
  verdict: IntentVerdict;
  reason: string;
}

// ─── Module E: Quality Validation ──────────────────────────────────────────

export interface QualityResult {
  score: number;
  issues: string[];
}

// ─── Module F: Aggregation ──────────────────────────────────────────────────

export interface ScoredChunk {
  chunkId: string;
  /** 0–100 */
  qualityScore: number;
  /** 0–1 */
  extractionConfidence: number;
}

export type Decision = "proceed" | "confirm-with-user" | "block";

export interface DecisionResult {
  decision: Decision;
  reason: string;
  /** Short plain-English verdict for the result card headline */
  headline: string;
  /** Ordered list of concrete things the user can do next */
  nextSteps: NextStep[];
}


// ─── Module G: Orchestrator ─────────────────────────────────────────────────

export interface ValidationResult {
  finalScore: number;
  intentVerdict: IntentVerdict;
  intentSimilarity: number;
  decision: Decision;
  reason: string;
  pageBreakdown: {
    total: number;
    textNative: number;
    imageOnly: number;
    mixed: number;
  };
  sampledChunks: number;
  scoredChunks: ScoredChunk[];
  timings: {
    pdfLoad: number;
    ocr: number;
    chunking: number;
    intentCheck: number;
    qualityScoring: number;
    total: number;
  };
}

// ─── Progress Reporting ─────────────────────────────────────────────────────

export type PipelineStage =
  | "pdf-loading"
  | "page-classification"
  | "ocr"
  | "chunking"
  | "sampling"
  | "intent-check"
  | "quality-scoring"
  | "aggregation"
  | "done"
  | "error";

export interface ProgressEvent {
  stage: PipelineStage;
  message: string;
  progress?: number; // 0–100
  detail?: string;
}

// ─── Phase 1: PDF Pre-flight ────────────────────────────────────────────────

export type PreflightResult =
  | { ok: true; pageCount: number }
  | { ok: false; reason: string; actionableHint: string };

// ─── Phase 1: Language Detection ────────────────────────────────────────────

/** ISO 639-1 codes for languages supported by our Tesseract build */
export type SupportedLang = "eng" | "hin" | "spa" | "fra" | "deu" | "por" | "chi_sim" | "ara";

export interface LangDetectResult {
  /** Tesseract language code to pass to runOcrOnPage */
  tesseractLang: SupportedLang;
  /** Human-readable name for the UI banner */
  displayName: string;
  /** True if we detected a specific supported language */
  confident: boolean;
}

// ─── Phase 2: Intent Intelligence ───────────────────────────────────────────

/** Result of the deterministic vagueness check — runs before any LLM call */
export interface VaguenessResult {
  vague: boolean;
  reason: "too_short" | "all_generic" | "no_domain" | "ok";
  /** One-line suggestion to show in the UI, or empty string if not vague */
  suggestion: string;
}

/**
 * Structured intent produced by the LLM expansion call (Phase 2.2).
 * Used downstream for: refined embedding comparison, keyword-weighted sampling,
 * document-type-aware quality rubric, and the UI confirmation card.
 */
export interface ExpandedIntent {
  domain: string;
  use_case: string;
  expected_content_types: string[];
  refined_query: string;
  document_keywords: string[];
}

/** Detected document content type — drives quality rubric selection in Module E */
export type DocumentType = "prose" | "technical-code" | "statistical" | "legal" | "mixed";

// ─── Phase 3: Chunk Quality Gating ──────────────────────────────────────────

/**
 * Result of the deterministic pre-screen applied to each chunk before LLM scoring.
 * Skipped chunks still get a score entry so the aggregator sees the full picture.
 */
export interface ChunkPreScreenResult {
  /** If true, skip the LLM call and use autoScore directly */
  skip: boolean;
  /** Score to use when skipping (0-100) */
  autoScore: number;
  /** Human-readable reason shown in the issues list */
  skipReason: string;
}

// ─── Phase 4: Actionable Feedback ──────────────────────────────────────────────

/** One concrete action the user can take to improve their result */
export interface NextStep {
  priority: "high" | "medium";
  icon: string;   // emoji
  action: string; // specific, imperative instruction
}


