/**
 * src/pdfLoader.ts — Module A
 * PDF Loading & Page Classification
 *
 * For every page, decides: text-native | image-only | mixed?
 * Extracts text directly wherever possible — avoiding OCR unless truly needed.
 * This is the single biggest cost/time saver in the whole design.
 */

import type { PageClassification, PageResult } from "./types";

// pdfjs-dist is loaded dynamically to support both Node.js and browser environments.
// In the browser, it's loaded via CDN in index.html.
// In Node.js, it's required directly.
let pdfjsLib: any = null;

async function getPdfjsLib() {
  if (pdfjsLib) return pdfjsLib;

  if (typeof window === "undefined") {
    // Node.js environment
    pdfjsLib = await import("pdfjs-dist");
    // Disable the worker in Node.js — use the legacy build
    pdfjsLib.GlobalWorkerOptions.workerSrc = "";
  } else {
    // Browser environment — pdfjs is injected via CDN in index.html
    pdfjsLib = (window as any).pdfjsLib;
    if (!pdfjsLib) {
      throw new Error("pdfjs-dist not loaded. Make sure the CDN script is included in index.html.");
    }
  }

  return pdfjsLib;
}

/**
 * How many extractable characters a page must have to be considered text-native.
 * Tune this against real test documents — 100 chars is a safe starting point.
 */
const TEXT_DENSITY_THRESHOLD = 100;

/**
 * Loads a PDF from a Uint8Array, classifies every page, and extracts text
 * where possible. Only pages flagged `needsOCR` should go to Module B.
 */
export async function loadAndClassifyPdf(
  fileBuffer: Uint8Array,
  onProgress?: (pageNum: number, total: number) => void
): Promise<PageResult[]> {
  const lib = await getPdfjsLib();

  const loadingTask = lib.getDocument({ data: fileBuffer });
  const pdf = await loadingTask.promise;

  const results: PageResult[] = [];
  const total = pdf.numPages;

  for (let i = 1; i <= total; i++) {
    const page = await pdf.getPage(i);

    // ── Extract text layer ──────────────────────────────────────────────────
    const textContent = await page.getTextContent();
    const extractedText = textContent.items
      .map((item: any) => item.str)
      .join(" ")
      .trim();

    // ── Check for embedded raster images ───────────────────────────────────
    const opList = await page.getOperatorList();
    // OPS values: paintImageXObject = 85, paintInlineImageXObject = 86
    const IMAGE_OPS = [85, 86];
    const hasImageOps = opList.fnArray.some((op: number) => IMAGE_OPS.includes(op));

    // ── Classify ────────────────────────────────────────────────────────────
    let classification: PageClassification;
    let needsOCR: boolean;

    if (extractedText.length >= TEXT_DENSITY_THRESHOLD && !hasImageOps) {
      // Good text, no big embedded image → extract directly, free
      classification = "text-native";
      needsOCR = false;
    } else if (extractedText.length < TEXT_DENSITY_THRESHOLD && hasImageOps) {
      // Almost no text, but has an image → scan page, needs OCR
      classification = "image-only";
      needsOCR = true;
    } else {
      // Has both usable text AND embedded images (e.g., a contract with a scanned sig page)
      // Keep the text, but also OCR the image region for completeness
      classification = "mixed";
      needsOCR = extractedText.length < TEXT_DENSITY_THRESHOLD; // only OCR if text is sparse
    }

    results.push({ pageNumber: i, classification, extractedText, needsOCR });

    if (onProgress) onProgress(i, total);

    // Release page resources
    page.cleanup();
  }

  return results;
}

/**
 * Renders a PDF page to an HTMLCanvasElement (browser only).
 * Called by the browser orchestrator before OCR.
 */
export async function renderPageToCanvas(
  fileBuffer: Uint8Array,
  pageNumber: number,
  scale: number = 2.0 // higher scale = better OCR accuracy
): Promise<HTMLCanvasElement> {
  const lib = await getPdfjsLib();
  const pdf = await lib.getDocument({ data: fileBuffer }).promise;
  const page = await pdf.getPage(pageNumber);

  const viewport = page.getViewport({ scale });
  const canvas = document.createElement("canvas");
  canvas.width = viewport.width;
  canvas.height = viewport.height;

  const ctx = canvas.getContext("2d")!;
  await page.render({ canvasContext: ctx, viewport }).promise;
  page.cleanup();

  return canvas;
}
