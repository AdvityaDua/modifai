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
      chunks.push({
        id: `p${pageNumber}-c${idx++}`,
        text,
        sourceType,
        confidence,
        pageNumber,
      });
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

/**
 * Stratified sampling: pick chunks spread evenly across the document
 * (beginning, middle, end) rather than randomly or all in one place.
 *
 * Sample count uses sqrt-scaling with diminishing returns:
 *   sample_count = clamp(ceil(sqrt(total_pages)), min=3, max=15)
 *
 * This keeps validation cost low regardless of document length.
 */
export function stratifiedSample(allChunks: Chunk[]): Chunk[] {
  if (allChunks.length === 0) return [];

  const totalPages = new Set(allChunks.map((c) => c.pageNumber)).size;
  const sampleCount = Math.min(15, Math.max(3, Math.ceil(Math.sqrt(totalPages))));

  if (allChunks.length <= sampleCount) return allChunks;

  // Even step across the full chunk array for stratification
  const step = allChunks.length / sampleCount;
  const sampled: Chunk[] = [];

  for (let i = 0; i < sampleCount; i++) {
    sampled.push(allChunks[Math.floor(i * step)]);
  }

  return sampled;
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
