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

import type { QualityResult } from "./types";

/**
 * Score a single chunk's quality using the LLM rubric.
 * Returns a 0–100 score and a list of specific issues found.
 *
 * @param chunkText - The text excerpt to evaluate
 * @param apiKey - OpenRouter API key
 */
export async function scoreChunkQuality(
  chunkText: string,
  apiKey: string
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
          content: `Rate this document excerpt from 0–100 on three dimensions:
1. Specificity (is it specific and detailed, not vague boilerplate?)
2. Grounding (does it contain real facts, procedures, or domain knowledge — not just filler?)
3. Readability (is it well-formatted, not garbled OCR noise or encoding errors?)

Combine these into a single overall score from 0–100.
Also list up to 3 specific issues you found (or an empty array if there are none).

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
  onChunkScored?: (index: number, total: number, score: number) => void
): Promise<Array<{ chunkId: string; qualityScore: number; extractionConfidence: number; issues: string[] }>> {
  const results = await Promise.all(
    chunks.map(async (chunk, i) => {
      const quality = await scoreChunkQuality(chunk.text, apiKey);
      if (onChunkScored) onChunkScored(i + 1, chunks.length, quality.score);
      return {
        chunkId: chunk.id,
        qualityScore: quality.score,
        extractionConfidence: chunk.confidence,
        issues: quality.issues,
      };
    })
  );
  return results;
}
