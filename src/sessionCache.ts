/**
 * src/sessionCache.ts — Phase 4.3
 * Session Content Hash & Re-upload Detection
 *
 * Hashes the file content using SubtleCrypto (browser-native, zero deps).
 * Caches OCR results, chunks, and the last validation result in sessionStorage.
 *
 * Cache entry expires after CACHE_TTL_MS (30 minutes).
 * On tab close, sessionStorage is cleared automatically by the browser.
 *
 * ponytail: sessionStorage only — no localStorage, no server persistence.
 *   Avoids privacy concerns of storing document content across sessions.
 *   Upgrade to localStorage with explicit user consent if persistence is needed.
 */

import type { OcrResult, Chunk, ValidationResult } from "./types";

const CACHE_KEY_PREFIX = "modifai_session_";
const CACHE_TTL_MS = 30 * 60 * 1000; // 30 minutes

export interface SessionCacheEntry {
  fileHash: string;
  timestamp: number;
  /** OCR results — reusable when only the intent changes */
  ocrResults: OcrResult[];
  /** All chunks built from this file — reusable across intent changes */
  allChunks: Chunk[];
  /** Full validation result from the last run */
  lastValidationResult: ValidationResult;
  /** Intent string used in the last run — detect if intent changed */
  lastIntent: string;
}

// ─── Hash ────────────────────────────────────────────────────────────────────

/**
 * Compute a hex SHA-256 fingerprint of the file's ArrayBuffer.
 * Uses the browser's SubtleCrypto — no polyfill needed on any modern browser.
 * Takes ~5-20ms for a 10MB file.
 */
export async function hashFile(arrayBuffer: ArrayBuffer): Promise<string> {
  const hashBuffer = await crypto.subtle.digest("SHA-256", arrayBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

// ─── Read / write ─────────────────────────────────────────────────────────────

function storageKey(hash: string): string {
  return CACHE_KEY_PREFIX + hash;
}

/**
 * Look up a cached entry by file hash.
 * Returns null if not found or if the entry has expired.
 */
export function getCacheEntry(fileHash: string): SessionCacheEntry | null {
  try {
    const raw = sessionStorage.getItem(storageKey(fileHash));
    if (!raw) return null;

    const entry: SessionCacheEntry = JSON.parse(raw);
    if (Date.now() - entry.timestamp > CACHE_TTL_MS) {
      sessionStorage.removeItem(storageKey(fileHash));
      return null;
    }
    return entry;
  } catch {
    return null; // JSON parse failure or sessionStorage unavailable
  }
}

/**
 * Store a cache entry. Silently ignores storage quota errors — the pipeline
 * will just re-run on the next upload, which is fine.
 */
export function setCacheEntry(entry: SessionCacheEntry): void {
  try {
    sessionStorage.setItem(storageKey(entry.fileHash), JSON.stringify(entry));
  } catch {
    // QuotaExceededError — cache is a nice-to-have, not critical
    console.warn("[sessionCache] Could not write to sessionStorage — quota exceeded or unavailable.");
  }
}

/**
 * Purge all expired ModifAI cache entries from sessionStorage.
 * Called opportunistically when a new file is selected.
 */
export function pruneExpiredEntries(): void {
  try {
    const keysToRemove: string[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i);
      if (!key?.startsWith(CACHE_KEY_PREFIX)) continue;
      const raw = sessionStorage.getItem(key);
      if (!raw) continue;
      try {
        const entry: SessionCacheEntry = JSON.parse(raw);
        if (Date.now() - entry.timestamp > CACHE_TTL_MS) keysToRemove.push(key);
      } catch {
        keysToRemove.push(key!); // malformed entry — remove it
      }
    }
    keysToRemove.forEach((k) => sessionStorage.removeItem(k));
    if (keysToRemove.length > 0) {
      console.log(`[sessionCache] Pruned ${keysToRemove.length} expired cache entries.`);
    }
  } catch {
    // sessionStorage unavailable — skip silently
  }
}

// ─── Age formatting ──────────────────────────────────────────────────────────

/**
 * Human-readable age string for the UI banner.
 * e.g. "2 minutes ago", "23 minutes ago"
 */
export function cacheEntryAge(entry: SessionCacheEntry): string {
  const mins = Math.floor((Date.now() - entry.timestamp) / 60_000);
  if (mins < 1) return "just now";
  if (mins === 1) return "1 minute ago";
  return `${mins} minutes ago`;
}
