/**
 * src/chunker.ts — Module C
 * Semantic Chunking & Stratified Sampling
 *
 * Two separate jobs:
 *  A) Chunking — split text into semantically coherent pieces (paragraph-first, sentence fallback)
 *  B) Sampling — pick which chunks to run validation checks on (sqrt-scaled, stratified)
 *
 * IMPORTANT: Do NOT mix OCR'd content and text-native content in the same chunk.
 * Keep them separate so quality scoring isn't muddied by mixing clean and noisy sources.
 */

import type { Chunk } from "./types";

// ─── Phase 3.1: Minimum quality filter ───────────────────────────────────────────

const MIN_CHUNK_WORDS = 20;   // fewer than this is almost never meaningful content
const MIN_CHUNK_CHARS = 100;  // absolute floor

// Patterns that identify non-content chunks (headers, TOC lines, page numbers)
const TOC_PATTERN    = /^(\d+\.?\s{1,5}.{3,60}\s+\d{1,4}\s*)+$/m;
const HEADER_PATTERN = /^[A-Z][A-Z\s]{0,40}$/;    // e.g. "CHAPTER THREE"
const PAGE_NUM_PATTERN = /^\s*\d{1,4}\s*$/;        // just a number

/**
 * Returns true if the chunk has enough substance to be worth scoring.
 * Drops headers, page numbers, TOC lines, and anything under the word/char floor.
 *
 * ponytail: regex + word count — covers 95% of junk chunks with zero cost.
 *   Add a perplexity check (small language model) if more precision is needed.
 */
function isSubstantiveChunk(text: string): boolean {
  const t = text.trim();
  if (t.length < MIN_CHUNK_CHARS) return false;
  if (t.split(/\s+/).length < MIN_CHUNK_WORDS) return false;
  if (PAGE_NUM_PATTERN.test(t)) return false;
  if (HEADER_PATTERN.test(t)) return false;
  if (TOC_PATTERN.test(t)) return false;
  return true;
}

/** Roughly ~512 tokens — matches the rest of the ModifAI pipeline */
const MAX_CHUNK_CHARS = 2000;

/** ~10% overlap context to avoid losing meaning at boundaries */
const OVERLAP_CHARS = 200;

/**
 * Split a page's text into semantically coherent chunks.
 * Uses paragraph boundaries first, then sentence boundaries for oversized paragraphs.
 *
 * Every chunk is tagged with:
 *  - sourceType: "text-native" | "ocr"
 *  - confidence: 1.0 for text-native, Tesseract averageConfidence/100 for OCR
 */
export function chunkText(
  pageText: string,
  pageNumber: number,
  sourceType: "text-native" | "ocr",
  confidence: number
): Chunk[] {
  if (!pageText || pageText.trim().length === 0) return [];

  // Split on paragraph breaks (one or more blank lines)
  const paragraphs = pageText
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0);

  const chunks: Chunk[] = [];
  let buffer = "";
  let idx = 0;

  const flushBuffer = () => {
    const text = buffer.trim();
    if (text.length > 0) {
      // Phase 3.1: drop non-substantive chunks before they enter the pipeline
      if (!isSubstantiveChunk(text)) {
        console.log(`[Chunker] Filtered chunk p${pageNumber}-c${idx} (too short / header / TOC): "${text.substring(0, 50)}..."`);
        buffer = "";
        return;
      }
      const chunk = {
        id: `p${pageNumber}-c${idx++}`,
        text,
        sourceType,
        confidence,
        pageNumber,
      };
      console.log(`[Chunker] Created chunk ${chunk.id} (${chunk.sourceType}, conf: ${chunk.confidence.toFixed(2)})`);
      console.log(`          Text: "${chunk.text.substring(0, 60).replace(/\n/g, " ")}..."`);
      chunks.push(chunk);
    }
    buffer = "";
  };

  for (const para of paragraphs) {
    // If this paragraph alone is oversized, split it by sentences first
    const segments = para.length > MAX_CHUNK_CHARS ? splitBySentences(para) : [para];

    for (const segment of segments) {
      if ((buffer + "\n\n" + segment).length > MAX_CHUNK_CHARS && buffer.length > 0) {
        // Save overlap context for the next chunk
        const overlap = buffer.slice(-OVERLAP_CHARS);
        flushBuffer();
        buffer = overlap + "\n\n" + segment;
      } else {
        buffer = buffer.length > 0 ? buffer + "\n\n" + segment : segment;
      }
    }
  }

  flushBuffer();
  return chunks;
}

/**
 * Split a paragraph into sentences as a fallback for very long paragraphs.
 * Uses a simple regex that handles most English punctuation.
 */
function splitBySentences(text: string): string[] {
  const sentences = text.match(/[^.!?]+[.!?]+(?:\s|$)/g) || [text];
  const groups: string[] = [];
  let current = "";

  for (const sentence of sentences) {
    if ((current + sentence).length > MAX_CHUNK_CHARS && current.length > 0) {
      groups.push(current.trim());
      current = sentence;
    } else {
      current += sentence;
    }
  }

  if (current.trim().length > 0) groups.push(current.trim());
  return groups;
}

// ─── Phase 3.2: Relevance-weighted sampling ────────────────────────────────────────

/**
 * Hybrid sample: 60% by keyword relevance (for niche-content-in-large-doc use case),
 * 40% by stratified position (to ensure beginning / middle / end coverage).
 *
 * Falls back to pure positional sampling when:
 *  - no keywords provided, or
 *  - no chunks score any keyword hits (completely off-topic document — will correctly
 *    score as low intent match anyway)
 *
 * Sample count formula unchanged: clamp(ceil(sqrt(total_pages)), 3, 15)
 *
 * ponytail: keyword hit counting — instant, zero cost, covers the holistic-doc case.
 *   Add embedding-based selection if keyword recall proves insufficient.
 */
export function stratifiedSample(allChunks: Chunk[], keywords: string[] = []): Chunk[] {
  if (allChunks.length === 0) return [];

  const totalPages = new Set(allChunks.map((c) => c.pageNumber)).size;
  const sampleCount = Math.min(15, Math.max(3, Math.ceil(Math.sqrt(totalPages))));

  if (allChunks.length <= sampleCount) return allChunks;

  // ── Positional baseline (always computed) ──────────────────────────────────
  const positionalCount = keywords.length > 0 ? Math.ceil(sampleCount * 0.4) : sampleCount;
  const step = allChunks.length / positionalCount;
  const positional = Array.from({ length: positionalCount }, (_, i) =>
    allChunks[Math.floor(i * step)]
  );

  if (keywords.length === 0) return positional;

  // ── Keyword relevance scoring ─────────────────────────────────────────────
  const normalised = keywords.map((k) => k.toLowerCase());

  const scored = allChunks.map((chunk) => {
    const lower = chunk.text.toLowerCase();
    const hits = normalised.reduce((n, kw) => n + (lower.includes(kw) ? 1 : 0), 0);
    return { chunk, hits };
  });

  const topHits = scored
    .filter((s) => s.hits > 0)
    .sort((a, b) => b.hits - a.hits);

  // No keyword matches at all — fall back to pure positional
  if (topHits.length === 0) {
    console.log("[Chunker] No keyword matches — falling back to positional sampling.");
    const fallbackStep = allChunks.length / sampleCount;
    return Array.from({ length: sampleCount }, (_, i) => allChunks[Math.floor(i * fallbackStep)]);
  }

  const relevantCount = sampleCount - positionalCount;
  const relevant = topHits.slice(0, relevantCount).map((s) => s.chunk);

  // Merge, deduplicate by id
  const seen = new Set<string>();
  const merged: Chunk[] = [];
  for (const c of [...relevant, ...positional]) {
    if (!seen.has(c.id)) { seen.add(c.id); merged.push(c); }
  }

  console.log(`[Chunker] Sample: ${relevant.length} keyword-matched + ${positional.length} positional = ${merged.length} unique chunks.`);
  return merged;
}

/**
 * Helper: given all page results (text + OCR), produce a flat list of all chunks
 * with correct sourceType and confidence tags.
 */
export function buildAllChunks(
  pages: Array<{
    pageNumber: number;
    extractedText: string;
    needsOCR: boolean;
    ocrResult?: { text: string; averageConfidence: number };
  }>
): Chunk[] {
  const allChunks: Chunk[] = [];

  for (const page of pages) {
    if (!page.needsOCR && page.extractedText.trim().length > 0) {
      // Text-native — high confidence
      allChunks.push(...chunkText(page.extractedText, page.pageNumber, "text-native", 1.0));
    } else if (page.ocrResult && page.ocrResult.text.trim().length > 0) {
      // OCR result — confidence normalized to 0–1
      const confidence = page.ocrResult.averageConfidence / 100;
      allChunks.push(...chunkText(page.ocrResult.text, page.pageNumber, "ocr", confidence));
    }
    // Mixed pages: if we have extractedText, chunk it as text-native too
    if (page.needsOCR && page.extractedText.trim().length >= 100) {
      allChunks.push(...chunkText(page.extractedText, page.pageNumber, "text-native", 1.0));
    }
  }

  return allChunks;
}
