/**
 * src/pdfGuard.ts — Phase 1.1
 * PDF Pre-flight Validation
 *
 * Runs synchronously on the raw file BEFORE pdf.js touches it.
 * Returns early with a human-readable hint on every failure class.
 * Zero dependencies — uses only the browser's native ArrayBuffer APIs.
 */

import type { PreflightResult } from "./types";

const MAX_BYTES = 100 * 1024 * 1024; // 100 MB

/**
 * Validate a PDF file before handing it to the pipeline.
 *
 * Call order in browserOrchestrator:
 *   1. pdfPreflight()        ← this file
 *   2. detectLanguage()
 *   3. loadAndClassifyPdf()
 */
export async function pdfPreflight(file: File): Promise<PreflightResult> {
  // ── 1. Size gate ────────────────────────────────────────────────────────────
  if (file.size > MAX_BYTES) {
    return {
      ok: false,
      reason: "File too large",
      actionableHint:
        "This file is over 100 MB. Try compressing it with a tool like Smallpdf, or split it into smaller sections and validate each one.",
    };
  }

  // ── 2. Magic bytes — must start with "%PDF-" ────────────────────────────────
  // ponytail: reading only 5 bytes, not the full file
  const header = await file.slice(0, 5).arrayBuffer();
  const magic = new TextDecoder().decode(header);
  if (!magic.startsWith("%PDF")) {
    return {
      ok: false,
      reason: "Not a valid PDF",
      actionableHint:
        "This file doesn't appear to be a PDF. Re-export or re-save it as a PDF from your original application (Word: File → Save As → PDF, Google Docs: File → Download → PDF).",
    };
  }

  // ── 3. Load with pdf.js to catch password-protection and corruption ─────────
  // We depend on pdfjsLib being available in window (loaded in index.html).
  // In Node.js this guard is skipped — the orchestrator handles it separately.
  if (typeof window === "undefined") {
    return { ok: true, pageCount: -1 }; // Node.js: skip, let pdfLoader handle it
  }

  const lib = (window as any).pdfjsLib;
  if (!lib) {
    // pdf.js not yet loaded — let the orchestrator proceed; it will fail naturally
    return { ok: true, pageCount: -1 };
  }

  const arrayBuffer = await file.arrayBuffer();

  try {
    const pdf = await lib.getDocument({ data: new Uint8Array(arrayBuffer) }).promise;

    // ── 4. Empty document ──────────────────────────────────────────────────────
    if (pdf.numPages === 0) {
      return {
        ok: false,
        reason: "Empty PDF",
        actionableHint:
          "This PDF has no pages. Make sure you exported the right file — the document may be empty or the export failed.",
      };
    }

    return { ok: true, pageCount: pdf.numPages };
  } catch (err: any) {
    // pdf.js throws PasswordException for encrypted files
    if (err?.name === "PasswordException") {
      return {
        ok: false,
        reason: "Password-protected PDF",
        actionableHint:
          "This PDF is password-protected. Open it in your PDF viewer, go to File → Security (or Properties) → Remove Password, save a new copy, and re-upload.",
      };
    }

    // Any other load failure = corrupted or unsupported format
    return {
      ok: false,
      reason: "PDF could not be opened",
      actionableHint:
        "This PDF couldn't be read — it may be corrupted or use an unsupported format. Try re-exporting it from the original application. If it came from a scanner, try scanning again.",
    };
  }
}
