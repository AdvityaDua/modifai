/**
 * src/qualityValidator.ts — Module E
 * Data Quality Validation (LLM scoring)
 *
 * Scores sampled chunks on the same rubric the main pipeline's Critic Agent uses:
 *  - Specificity: not vague boilerplate
 *  - Grounding: contains real facts/procedures, not filler
 *  - Format: readable, not garbled OCR noise
 *
 * Uses a cheap small model via OpenRouter. Called once per sampled chunk.
 * (Not once per chunk in the whole document — only the stratified sample.)
 */

import type { QualityResult, DocumentType, ChunkPreScreenResult } from "./types";

// ─── Phase 3.3: Deterministic pre-screen ────────────────────────────────────────

// Ratio of non-alphanumeric, non-whitespace chars that indicates garbled OCR
const NOISE_CHAR_RATIO_THRESHOLD = 0.20;
// Minimum word count for a chunk to be worth an LLM call
const MIN_WORDS_FOR_LLM = 15;
// OCR confidence below this → auto-fail without LLM
const MIN_OCR_CONFIDENCE = 0.35;

/**
 * Deterministic pre-screen — runs before every LLM quality scoring call.
 *
 * Three fast checks, in order of cheapness:
 *  1. Word count floor  — < 15 words → clearly too sparse, auto-score 10
 *  2. Noise char ratio  — >20% garbage chars → garbled OCR, auto-score 5
 *  3. OCR confidence   — Tesseract < 35% → very low confidence, auto-score 15
 *
 * Chunks that pass all three go to the LLM scorer as normal.
 *
 * ponytail: three regex + arithmetic checks, zero cost.
 *   Add Shannon entropy check if garbled-but-lowercase text slips through.
 */
export function preScreenChunk(
  text: string,
  ocrConfidence: number  // 0–1; pass 1.0 for text-native pages
): ChunkPreScreenResult {
  const words = text.trim().split(/\s+/).filter(Boolean);

  // 1. Too sparse to score meaningfully
  if (words.length < MIN_WORDS_FOR_LLM) {
    return { skip: true, autoScore: 10, skipReason: "Chunk too sparse for quality scoring (< 15 words)." };
  }

  // 2. Noise character ratio (garbage OCR output)
  const nonAlphaNum = (text.match(/[^\w\s]/g) || []).length;
  const noiseRatio = nonAlphaNum / (text.length || 1);
  if (noiseRatio > NOISE_CHAR_RATIO_THRESHOLD) {
    return {
      skip: true,
      autoScore: 5,
      skipReason: `High noise character ratio (${(noiseRatio * 100).toFixed(0)}%) — likely garbled OCR output.`,
    };
  }

  // 3. Very low Tesseract confidence (OCR pages only)
  if (ocrConfidence < MIN_OCR_CONFIDENCE) {
    return {
      skip: true,
      autoScore: 15,
      skipReason: `Very low OCR confidence (${(ocrConfidence * 100).toFixed(0)}%) — text extraction may be unreliable.`,
    };
  }

  return { skip: false, autoScore: 0, skipReason: "" };
}


// ─── Document-type-aware rubric ────────────────────────────────────────────

function rubricForDocType(docType: DocumentType): string {
  switch (docType) {
    case "technical-code":
      return `Rate this technical document excerpt (0–100) on:
1. Completeness: does it fully explain the concept, function, or API being described?
2. Accuracy signals: does it use precise technical terminology and concrete examples?
3. Structure: is it logically organised (not garbled, not truncated mid-sentence)?
Do NOT penalise for low narrative readability — code and technical references are not prose.`;

    case "statistical":
      return `Rate this research/statistical document excerpt (0–100) on:
1. Data completeness: are variables, sample sizes, or methods described?
2. Precision: does it use defined statistical terms (mean, p-value, CI, etc.) correctly?
3. Coherence: is it free of garbled text or encoding errors?
Do NOT penalise for dense notation or non-narrative style.`;

    case "legal":
      return `Rate this legal document excerpt (0–100) on:
1. Clause completeness: are obligations, conditions, or parties clearly defined?
2. Specificity: are terms defined and not left vague?
3. Readability: is it free of garbled OCR or encoding errors?
Do NOT penalise for formal legal language or sentence length.`;

    default: // prose, mixed
      return `Rate this document excerpt (0–100) on:
1. Specificity: is it specific and detailed, not vague boilerplate?
2. Grounding: does it contain real facts, procedures, or domain knowledge — not just filler?
3. Readability: is it well-formatted, not garbled OCR noise or encoding errors?`;
  }
}


/**
 * Score a single chunk's quality using the LLM rubric.
 * Returns a 0–100 score and a list of specific issues found.
 *
 * @param chunkText - The text excerpt to evaluate
 * @param apiKey - OpenRouter API key
 */
export async function scoreChunkQuality(
  chunkText: string,
  apiKey: string,
  docType: DocumentType = "prose"  // Phase 2.3: rubric adapts to document type
): Promise<QualityResult> {
  const truncated = chunkText.slice(0, 2000); // cap input tokens

  const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "qwen/qwen-2.5-7b-instruct",
      messages: [
        {
          role: "user",
          content: `${rubricForDocType(docType)}

Combine these into a single overall score from 0–100.
Also list up to 3 specific issues found (or an empty array if there are none).

Excerpt:
"""${truncated}"""

Respond ONLY with valid JSON (no markdown, no extra text):
{"score": number, "issues": ["issue 1", "issue 2"]}`,
        },
      ],
      max_tokens: 200,
      temperature: 0.1,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`OpenRouter API error ${response.status}: ${errorText}`);
  }

  const data = await response.json();
  const raw = data.choices[0].message.content.trim();
  const cleaned = raw.replace(/```(?:json)?|```/g, "").trim();

  try {
    const parsed = JSON.parse(cleaned) as QualityResult;
    // Clamp score to [0, 100] in case the model goes out of range
    parsed.score = Math.max(0, Math.min(100, parsed.score));
    parsed.issues = Array.isArray(parsed.issues) ? parsed.issues.slice(0, 3) : [];
    return parsed;
  } catch {
    console.warn("[qualityValidator] Failed to parse LLM JSON, raw response:", raw);
    // Return a mid-range score so the pipeline doesn't hard-fail on a parse error
    return { score: 50, issues: ["Could not parse quality score from LLM response."] };
  }
}

/**
 * Score multiple chunks in parallel (one LLM call each).
 * For a handful of sampled chunks this is fine; larger batches should be rate-limited.
 *
 * @param chunks - Array of {id, text, confidence} objects to score
 * @param apiKey - OpenRouter API key
 * @param onChunkScored - Optional progress callback
 */
export async function scoreAllChunks(
  chunks: { id: string; text: string; confidence: number }[],
  apiKey: string,
  onChunkScored?: (index: number, total: number, score: number) => void,
  docType: DocumentType = "prose"  // Phase 2.3: passed from orchestrator
): Promise<Array<{ chunkId: string; qualityScore: number; extractionConfidence: number; issues: string[] }>> {
  const results = await Promise.all(
    chunks.map(async (chunk, i) => {
      // Phase 3.3: run deterministic pre-screen before spending an LLM call
      const preScreen = preScreenChunk(chunk.text, chunk.confidence);

      let qualityScore: number;
      let issues: string[];

      if (preScreen.skip) {
        // Short-circuit: no LLM call, log the reason
        qualityScore = preScreen.autoScore;
        issues = [preScreen.skipReason];
        console.log(`[qualityValidator] Pre-screen skipped chunk ${chunk.id}: ${preScreen.skipReason}`);
      } else {
        const quality = await scoreChunkQuality(chunk.text, apiKey, docType);
        qualityScore = quality.score;
        issues = quality.issues;
      }

      if (onChunkScored) onChunkScored(i + 1, chunks.length, qualityScore);
      return {
        chunkId: chunk.id,
        qualityScore,
        extractionConfidence: chunk.confidence,
        issues,
      };
    })
  );
  return results;
}
