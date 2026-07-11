/**
 * src/aggregator.ts — Module F
 * Aggregation & Threshold Decision
 *
 * Combines all quality scores into one final score, weighted by extraction confidence,
 * then applies threshold logic to decide: proceed | confirm-with-user | block
 *
 * Thresholds (70/45) are starting points — tune against real test documents.
 */

import type { ScoredChunk, Decision, DecisionResult, IntentVerdict, NextStep } from "./types";


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
  intentVerdict: IntentVerdict,
  domain = "",              // Phase 4.1: from expandedIntent.domain, optional
  lowOcrChunks = 0,         // Phase 4.1: count of chunks with low OCR confidence
  totalChunks = 0
): DecisionResult {
  const steps: NextStep[] = [];

  // ── 1. Intent mismatch: hard block ────────────────────────────────────────────────
  if (intentVerdict === "mismatch") {
    steps.push({
      priority: "high",
      icon: "📄",
      action: domain
        ? `Upload a document specifically about "${domain}". The document you uploaded appears to cover a different topic.`
        : "Upload a document that matches your stated goal, or update your intent description to match this document.",
    });
    steps.push({
      priority: "medium",
      icon: "✏️",
      action: "Edit your intent description to be more specific — include the exact domain and type of questions the assistant should answer.",
    });
    return {
      decision: "block",
      headline: "Document doesn't match your intent",
      reason: "The document does not appear to match what you said you want to build. Please upload a relevant document or update your intent description.",
      nextSteps: steps,
    };
  }

  // ── 2. High quality + clear intent: auto-proceed ───────────────────────────────
  if (finalScore >= 70 && intentVerdict === "match") {
    steps.push({
      priority: "medium",
      icon: "✅",
      action: `Your document is ready. ${totalChunks > 0 ? `${totalChunks} chunk(s)` : "Content"} will be passed to the ModifAI dataset generator.`,
    });
    return {
      decision: "proceed",
      headline: "Document looks great — ready to proceed",
      reason: "Document quality and intent match both look good.",
      nextSteps: steps,
    };
  }

  // ── 3. Borderline quality ────────────────────────────────────────────────────
  if (finalScore >= 45) {
    if (intentVerdict === "partial") {
      steps.push({
        priority: "high",
        icon: "✏️",
        action: domain
          ? `Your document covers "${domain}" broadly. Narrow your intent description to the specific section or topic that matters most.`
          : "Narrow your intent description to the specific section of the document you want the assistant to focus on.",
      });
    }
    if (lowOcrChunks > 0) {
      steps.push({
        priority: "high",
        icon: "🔄",
        action: `${lowOcrChunks} chunk(s) had low OCR confidence. Rescan at 300 DPI or higher with even lighting and no shadow across the text.`,
      });
    }
    steps.push({
      priority: "medium",
      icon: "📄",
      action: "If only part of the document is relevant, extract those pages into a new PDF and re-upload — this will improve both quality and intent match scores.",
    });
    const qualityNote =
      finalScore >= 60
        ? "Document quality is acceptable but not ideal."
        : "Document quality is borderline — some pages may not be fully usable.";
    const intentNote = intentVerdict === "partial" ? " Intent is a partial match — results may be less focused." : "";
    return {
      decision: "confirm-with-user",
      headline: "Borderline result — your call",
      reason: `${qualityNote}${intentNote} You can proceed, but results may be lower quality than expected.`,
      nextSteps: steps,
    };
  }

  // ── 4. Low quality: block ───────────────────────────────────────────────────────
  if (lowOcrChunks > 0) {
    steps.push({
      priority: "high",
      icon: "🔄",
      action: "Rescan at 300 DPI or higher. Use a flatbed scanner if available. Ensure even lighting and no shadow across the page.",
    });
  }
  steps.push({
    priority: "high",
    icon: "📄",
    action: "If this document is a template or a summary, upload the full, completed version with all the content filled in.",
  });
  steps.push({
    priority: "medium",
    icon: "🗜️",
    action: "Try re-exporting the PDF from the original application (Word: File → Save As → PDF). Some PDF printers produce poor-quality output.",
  });
  return {
    decision: "block",
    headline: "Document quality too low",
    reason: "Document quality is too low to produce reliable results. The document may be unreadable, too sparse, or corrupted by a poor scan.",
    nextSteps: steps,
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
