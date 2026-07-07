/**
 * src/ocrProcessor.ts — Module B
 * OCR Processing (Tesseract.js, runs in browser via WASM)
 *
 * Only called for pages flagged `needsOCR` by Module A.
 * Includes grayscale + binarization preprocessing to improve Tesseract accuracy.
 */

import type { OcrResult } from "./types";

/**
 * Preprocess a canvas image before OCR:
 *  1. Convert to grayscale
 *  2. Apply binarization (threshold at 150) → pure black/white
 *     (Tesseract handles pure B&W significantly better than greyscale)
 *
 * NOTE: For a hackathon, deskew is skipped unless test documents are actually rotated.
 * Grayscale + binarization gives most of the accuracy improvement.
 */
export function preprocessCanvas(canvas: HTMLCanvasElement): HTMLCanvasElement {
  const ctx = canvas.getContext("2d")!;
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const data = imageData.data;

  // Luminosity-weighted grayscale + hard threshold binarization
  for (let i = 0; i < data.length; i += 4) {
    const gray = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    const value = gray > 150 ? 255 : 0;
    data[i] = data[i + 1] = data[i + 2] = value;
    // Alpha unchanged
  }

  ctx.putImageData(imageData, 0, 0);
  return canvas;
}

/**
 * Run Tesseract.js OCR on a preprocessed canvas.
 * Returns the extracted text plus per-word confidence scores.
 *
 * Each call creates and terminates its own Tesseract worker — fine for a handful
 * of pages at hackathon scale. For large-scale use, maintain a worker pool.
 *
 * @param canvas - A canvas that has already been preprocessed by `preprocessCanvas()`
 * @param pageNumber - For tracking/logging
 * @param onProgress - Optional progress callback (0–100)
 */
export async function runOcrOnPage(
  canvas: HTMLCanvasElement,
  pageNumber: number,
  onProgress?: (pct: number) => void
): Promise<OcrResult> {
  // Dynamic import so Node.js can load it when not in a browser context
  const { createWorker } = await import("tesseract.js");

  const worker = await createWorker("eng", 1, {
    logger: onProgress
      ? (m: any) => {
          if (m.status === "recognizing text" && typeof m.progress === "number") {
            onProgress(Math.round(m.progress * 100));
          }
        }
      : undefined,
  });

  const { data } = await worker.recognize(canvas);
  await worker.terminate();

  const wordConfidences = data.words.map((w: any) => ({
    word: w.text,
    confidence: w.confidence,
  }));

  const averageConfidence =
    wordConfidences.length > 0
      ? wordConfidences.reduce((sum, w) => sum + w.confidence, 0) / wordConfidences.length
      : 0;

  return {
    pageNumber,
    text: data.text,
    averageConfidence,
    wordConfidences,
  };
}

/**
 * Runs OCR on multiple pages sequentially (safe for hackathon scale).
 * Logs timing per page so you can catch if OCR is running on too many pages.
 */
export async function runOcrOnPages(
  pages: { canvas: HTMLCanvasElement; pageNumber: number }[],
  onPageDone?: (result: OcrResult, index: number, total: number) => void
): Promise<OcrResult[]> {
  const results: OcrResult[] = [];

  for (let i = 0; i < pages.length; i++) {
    const { canvas, pageNumber } = pages[i];
    const t0 = performance.now();

    const preprocessed = preprocessCanvas(canvas);
    const result = await runOcrOnPage(preprocessed, pageNumber);

    const elapsed = ((performance.now() - t0) / 1000).toFixed(2);
    console.log(
      `[OCR] Page ${pageNumber}: conf=${result.averageConfidence.toFixed(1)}, elapsed=${elapsed}s`
    );

    results.push(result);
    if (onPageDone) onPageDone(result, i, pages.length);
  }

  return results;
}
