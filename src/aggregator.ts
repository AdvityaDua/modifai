/**
 * src/aggregator.ts — Module F
 * Aggregation & Threshold Decision
 *
 * Combines all quality scores into one final score, weighted by extraction confidence,
 * then applies threshold logic to decide: proceed | confirm-with-user | block
 *
 * Thresholds (70/45) are starting points — tune against real test documents.
 */

import type { ScoredChunk, Decision, DecisionResult, IntentVerdict } from "./types";

/**
 * Compute the confidence-weighted mean quality score.
 * Chunks from text-native sources (confidence=1.0) get full weight.
 * OCR'd chunks with low Tesseract confidence get downweighted.
 *
 * @param scoredChunks - Array of {qualityScore (0–100), extractionConfidence (0–1)}
 * @returns Weighted average quality score in [0, 100]
 */
export function aggregateScore(scoredChunks: ScoredChunk[]): number {
  if (scoredChunks.length === 0) return 0;

  const weightedSum = scoredChunks.reduce(
    (sum, c) => sum + c.qualityScore * c.extractionConfidence,
    0
  );
  const totalWeight = scoredChunks.reduce((sum, c) => sum + c.extractionConfidence, 0);

  return totalWeight > 0 ? weightedSum / totalWeight : 0;
}

/**
 * Apply the threshold decision logic.
 *
 * Priority:
 *  1. Intent mismatch ALWAYS blocks, regardless of quality score.
 *  2. High quality + intent match → proceed automatically.
 *  3. Borderline quality → show user a confirmation prompt.
 *  4. Low quality → block with a specific explanation.
 *
 * @param finalScore - Aggregated quality score [0, 100]
 * @param intentVerdict - "match" | "partial" | "mismatch"
 */
export function decide(
  finalScore: number,
  intentVerdict: IntentVerdict
): DecisionResult {
  // ── 1. Intent mismatch: hard block ─────────────────────────────────────────
  if (intentVerdict === "mismatch") {
    return {
      decision: "block",
      reason:
        "The document does not appear to match what you said you want to build. " +
        "Please upload a document that matches your stated intent, or update your intent description.",
    };
  }

  // ── 2. High quality + clear intent match: auto-proceed ─────────────────────
  if (finalScore >= 70 && intentVerdict === "match") {
    return {
      decision: "proceed",
      reason: "Document quality and intent match both look good. Proceeding to the main pipeline.",
    };
  }

  // ── 3. Borderline quality (with match or partial intent) ────────────────────
  if (finalScore >= 45) {
    const qualityNote =
      finalScore >= 60
        ? "Document quality is acceptable but not ideal."
        : "Document quality is borderline — some pages may not be fully usable.";
    const intentNote =
      intentVerdict === "partial"
        ? " The document intent is a partial match — results may be less focused."
        : "";
    return {
      decision: "confirm-with-user",
      reason: `${qualityNote}${intentNote} You can proceed anyway, but results may be lower quality than expected.`,
    };
  }

  // ── 4. Low quality: block ───────────────────────────────────────────────────
  return {
    decision: "block",
    reason:
      "Document quality is too low to produce reliable results. " +
      "The document may be mostly unreadable, too sparse, or heavily corrupted by poor scanning. " +
      "Please try a higher-quality scan or a different document.",
  };
}

/**
 * Generate a human-readable summary of the validation results for display in the UI.
 */
export function buildSummary(
  finalScore: number,
  intentVerdict: IntentVerdict,
  intentSimilarity: number,
  scoredChunks: ScoredChunk[]
): {
  qualityGrade: "A" | "B" | "C" | "D" | "F";
  intentGrade: "Strong Match" | "Partial Match" | "Mismatch";
  averageOcrConfidence: number | null;
  lowConfidenceChunks: number;
} {
  const qualityGrade =
    finalScore >= 85
      ? "A"
      : finalScore >= 70
      ? "B"
      : finalScore >= 55
      ? "C"
      : finalScore >= 40
      ? "D"
      : "F";

  const intentGrade =
    intentVerdict === "match"
      ? "Strong Match"
      : intentVerdict === "partial"
      ? "Partial Match"
      : "Mismatch";

  const ocrChunks = scoredChunks.filter((c) => c.extractionConfidence < 1.0);
  const averageOcrConfidence =
    ocrChunks.length > 0
      ? ocrChunks.reduce((sum, c) => sum + c.extractionConfidence, 0) / ocrChunks.length
      : null;

  const lowConfidenceChunks = scoredChunks.filter((c) => c.extractionConfidence < 0.6).length;

  return { qualityGrade, intentGrade, averageOcrConfidence, lowConfidenceChunks };
}
