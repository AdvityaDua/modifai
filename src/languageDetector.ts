/**
 * src/languageDetector.ts — Phase 1.2
 * Document Language Detection
 *
 * Runs on a text sample extracted by Module A (text-native pages only).
 * For image-only documents, returns English as the default — we can't
 * detect language before OCR, and we can't OCR before knowing the language.
 * In that case, the UI banner asks the user to confirm.
 *
 * Detection strategy:
 *   - Uses script/character-range analysis directly on the text sample.
 *   - No external library needed: Unicode block ranges identify the script
 *     reliably for our 8 supported languages without the 400KB franc bundle.
 *
 * ponytail: skipped franc dependency — character range detection is a
 *   one-function solution that covers our 8 languages with no bundle cost.
 *   Add franc if we expand to 30+ languages.
 */

import type { LangDetectResult, SupportedLang } from "./types";

/** Languages we can actually pass to Tesseract.js */
const SUPPORTED: Record<SupportedLang, string> = {
  eng: "English",
  hin: "Hindi",
  spa: "Spanish",
  fra: "French",
  deu: "German",
  por: "Portuguese",
  chi_sim: "Chinese (Simplified)",
  ara: "Arabic",
};

const DEFAULT: LangDetectResult = {
  tesseractLang: "eng",
  displayName: "English",
  confident: false,
};

/**
 * Detect language from a plain-text sample using Unicode script ranges.
 * Fast, zero-dependency, covers our 8 supported languages.
 *
 * @param textSample  First ~500 chars of extractable text from the document
 */
export function detectLanguage(textSample: string): LangDetectResult {
  if (!textSample || textSample.trim().length < 20) return DEFAULT;

  const sample = textSample.slice(0, 500);

  // Count characters in each Unicode block
  let arabic = 0, devanagari = 0, cjk = 0, latin = 0;

  for (const ch of sample) {
    const cp = ch.codePointAt(0)!;
    if (cp >= 0x0600 && cp <= 0x06FF) arabic++;           // Arabic block
    else if (cp >= 0x0900 && cp <= 0x097F) devanagari++;  // Devanagari (Hindi)
    else if (
      (cp >= 0x4E00 && cp <= 0x9FFF) ||                   // CJK Unified Ideographs
      (cp >= 0x3400 && cp <= 0x4DBF)                      // CJK Extension A
    ) cjk++;
    else if (cp >= 0x0041 && cp <= 0x007A) latin++;       // Basic Latin A–z
  }

  const total = sample.replace(/\s/g, "").length || 1;

  // Script thresholds: if >15% of non-whitespace chars are in a script block,
  // it's the dominant script.
  if (arabic / total > 0.15)     return { tesseractLang: "ara",     displayName: "Arabic",                confident: true };
  if (devanagari / total > 0.15) return { tesseractLang: "hin",     displayName: "Hindi",                 confident: true };
  if (cjk / total > 0.10)        return { tesseractLang: "chi_sim", displayName: "Chinese (Simplified)", confident: true };

  // For Latin-script languages, look for language-specific diacritics / common words
  if (latin / total > 0.4) {
    // Spanish: ñ, ¿, ¡ or high-frequency Spanish words
    if (/[ñÑ¿¡]/.test(sample) || /\b(para|con|una|que|los|las|del)\b/i.test(sample))
      return { tesseractLang: "spa", displayName: "Spanish", confident: true };

    // French: é/è/ê/à/ù/œ or high-frequency French words
    if (/[éèêëàùûœ]/i.test(sample) || /\b(les|des|une|pour|dans|avec|que)\b/i.test(sample))
      return { tesseractLang: "fra", displayName: "French", confident: true };

    // German: ä/ö/ü/ß or high-frequency German words
    if (/[äöüÄÖÜß]/.test(sample) || /\b(und|der|die|das|ist|nicht|auch)\b/i.test(sample))
      return { tesseractLang: "deu", displayName: "German", confident: true };

    // Portuguese: ã/ô/ç or high-frequency Portuguese words
    if (/[ãõô]/i.test(sample) || /\b(para|com|uma|que|não|por|mas)\b/i.test(sample))
      return { tesseractLang: "por", displayName: "Portuguese", confident: true };

    // Default Latin → English (most common, safest fallback)
    return { tesseractLang: "eng", displayName: "English", confident: true };
  }

  // Couldn't identify — default to English, signal low confidence so UI can warn
  return DEFAULT;
}

/**
 * Returns the human-readable display name for a given Tesseract language code.
 * Used by the UI banner.
 */
export function langDisplayName(code: SupportedLang): string {
  return SUPPORTED[code] ?? "Unknown";
}
