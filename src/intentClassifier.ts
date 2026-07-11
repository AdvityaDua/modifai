/**
 * src/intentClassifier.ts — Module D
 * Intent Classification (embeddings first, LLM only if unsure)
 *
 * Step 1 — Free local check: embed user intent + sample text, compute cosine similarity.
 * Step 2 — Only escalate to a paid LLM call if similarity is in the ambiguous 0.4–0.7 band.
 *
 * Clear matches (>0.7) and clear mismatches (<0.4) never trigger an LLM call.
 */

import type { IntentVerdict, IntentCheckResult, LLMIntentResult, VaguenessResult, ExpandedIntent } from "./types";

// ─── Vagueness detection ─────────────────────────────────────────────────────

const GENERIC_TERMS = new Set([
  "chatbot", "assistant", "ai", "smart", "helpful", "automation",
  "tool", "bot", "system", "app", "application", "solution", "service",
]);

/**
 * Deterministic vagueness check — runs in-browser with zero cost, before any LLM call.
 * Returns a suggestion only when vague; the orchestrator shows it as a soft warning, not a block.
 *
 * ponytail: word-list + length heuristic — covers the vast majority of under-specified intents.
 *   Add semantic vagueness detection (embed + compare to a "generic" centroid) if false-negative
 *   rate becomes a problem in production.
 */
export function checkIntentVagueness(intent: string): VaguenessResult {
  const trimmed = intent.trim();
  const words = trimmed.toLowerCase().split(/\s+/).filter(Boolean);

  if (words.length < 4) {
    return {
      vague: true,
      reason: "too_short",
      suggestion:
        "Add more detail. For example: instead of \"HR assistant\", try \"an assistant that answers employee questions about leave policy and onboarding procedures\".",
    };
  }

  const isAllGeneric = words.every((w) => GENERIC_TERMS.has(w));
  if (isAllGeneric) {
    return {
      vague: true,
      reason: "all_generic",
      suggestion:
        "Your description uses only general terms. Add the specific topic or domain — what kind of questions should this assistant answer?",
    };
  }

  // Require at least one word > 4 chars that isn't a generic term (a real domain noun)
  const hasSubstantiveWord = words.some((w) => w.length > 4 && !GENERIC_TERMS.has(w));
  if (!hasSubstantiveWord) {
    return {
      vague: true,
      reason: "no_domain",
      suggestion:
        "Include the specific subject area. For example: \"customer returns\", \"employee handbook\", \"API documentation\", \"financial reports\".",
    };
  }

  return { vague: false, reason: "ok", suggestion: "" };
}

// ─── Intent expansion ────────────────────────────────────────────────────────

const EXPANSION_PROMPT = (intent: string) => `\
A user wants to build an AI assistant from a document they will upload.
Their description: "${intent}"

Expand this into a structured JSON object. Be specific and domain-aware.

{
  "domain": "the specific subject area (e.g. HR policy, e-commerce returns, Python API docs)",
  "use_case": "one sentence: what will the assistant do for the end user",
  "expected_content_types": ["2-4 types of content the source document should contain"],
  "refined_query": "a single sentence describing what an ideal source document looks like — use domain-specific vocabulary",
  "document_keywords": ["6-8 keywords likely to appear in a matching document"]
}

Respond ONLY with valid JSON. No markdown, no extra text.`;

// ponytail: plain Map — session-lived, same intent = free hit, no TTL needed.
const _expandCache = new Map<string, ExpandedIntent>();

/**
 * Expand the user's raw intent into a structured ExpandedIntent object via one LLM call.
 *
 * Returns null if the API call fails — callers should fall back to using the raw intent string.
 * The refined_query replaces the raw intent for embedding; document_keywords feed Phase 3 sampling.
 */
export async function expandIntent(
  userIntent: string,
  apiKey: string
): Promise<ExpandedIntent | null> {
  // Cache hit — skip LLM call
  const cached = _expandCache.get(userIntent.trim());
  if (cached) {
    console.log("[intentClassifier] expandIntent cache hit — reusing previous result.");
    return cached;
  }

  try {
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "meta-llama/llama-3.1-8b-instruct",
        messages: [{ role: "user", content: EXPANSION_PROMPT(userIntent) }],
        max_tokens: 300,
        temperature: 0.2,
      }),
    });

    if (!response.ok) return null;

    const data = await response.json();
    const raw = data.choices[0].message.content.trim();
    const cleaned = raw.replace(/```(?:json)?|```/g, "").trim();
    const parsed = JSON.parse(cleaned) as ExpandedIntent;

    // Validate required fields — defensive against partial LLM responses
    if (
      typeof parsed.domain !== "string" ||
      typeof parsed.refined_query !== "string" ||
      !Array.isArray(parsed.document_keywords)
    ) {
      console.warn("[intentClassifier] expandIntent: unexpected shape, falling back.", parsed);
      return null;
    }

    _expandCache.set(userIntent.trim(), parsed);
    return parsed;
  } catch (err) {
    console.warn("[intentClassifier] expandIntent failed, using raw intent.", err);
    return null;
  }
}


// Singleton embedder — loaded once, reused across calls
let embedder: any = null;

/**
 * Lazily initialise the Transformers.js pipeline.
 * Downloads `Xenova/all-MiniLM-L6-v2` on first call (cached after that).
 * Runs fully in-browser or in Node.js — no API key, no cost.
 */
async function getEmbedder(): Promise<any> {
  if (embedder) return embedder;

  const { pipeline } = await import("@xenova/transformers");
  embedder = await pipeline("feature-extraction", "Xenova/all-MiniLM-L6-v2");
  return embedder;
}

/**
 * Compute the cosine similarity between two numeric vectors.
 * Returns a value in [-1, 1]; for normalised sentence embeddings practically [0, 1].
 */
function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length) throw new Error("Vector dimension mismatch");
  const dot = a.reduce((sum, v, i) => sum + v * b[i], 0);
  const normA = Math.sqrt(a.reduce((sum, v) => sum + v * v, 0));
  const normB = Math.sqrt(b.reduce((sum, v) => sum + v * v, 0));
  if (normA === 0 || normB === 0) return 0;
  return dot / (normA * normB);
}

/**
 * Embed a text string into a dense vector using the local MiniLM model.
 * Mean-pooled, L2-normalised — ready for cosine similarity comparison.
 */
export async function embedText(text: string): Promise<number[]> {
  const embed = await getEmbedder();
  const output = await embed(text, { pooling: "mean", normalize: true });
  return Array.from(output.data as Float32Array);
}

/**
 * Run the free, local intent check.
 *
 * @param userIntent - What the user says they want to build ("I want an HR policy assistant")
 * @param sampleText - Concatenated text from the stratified sample chunks
 * @returns similarity score and whether an LLM call is warranted
 */
export async function checkIntentMatch(
  userIntent: string,
  sampleText: string
): Promise<IntentCheckResult> {
  // Embed both in parallel — free, instant
  const [intentVec, sampleVec] = await Promise.all([
    embedText(userIntent),
    embedText(sampleText.slice(0, 8000)), // cap to avoid model context overflow
  ]);

  const similarity = cosineSimilarity(intentVec, sampleVec);

  // Thresholds from the build manual (§9) — tune against your real test docs
  const CLEAR_MATCH_THRESHOLD = 0.7;
  const CLEAR_MISMATCH_THRESHOLD = 0.4;
  const needsLLMCheck = similarity >= CLEAR_MISMATCH_THRESHOLD && similarity <= CLEAR_MATCH_THRESHOLD;

  return { similarity, needsLLMCheck };
}

/**
 * Determine intent verdict from similarity score alone (no LLM).
 * Used when the score is outside the ambiguous band.
 */
export function similarityToVerdict(similarity: number): IntentVerdict {
  if (similarity > 0.7) return "match";
  if (similarity < 0.4) return "mismatch";
  return "partial";
}

/**
 * LLM escalation — only called for the ambiguous 0.4–0.7 similarity band.
 * Uses a cheap, small model via OpenRouter to give a definitive verdict.
 */
export async function llmIntentVerdict(
  userIntent: string,
  sampleText: string,
  apiKey: string
): Promise<LLMIntentResult> {
  const truncatedSample = sampleText.slice(0, 3000); // keep token cost small

  const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "meta-llama/llama-3.1-8b-instruct",
      messages: [
        {
          role: "user",
          content: `A user wants to build: "${userIntent}"\n\nHere is a sample from their uploaded document:\n"""${truncatedSample}"""\n\nDoes this document match what the user wants to build?\nRespond ONLY with valid JSON (no markdown, no extra text):\n{"verdict": "match" | "partial" | "mismatch", "reason": "one short sentence explaining why"}`,
        },
      ],
      max_tokens: 150,
      temperature: 0.1, // low temperature for consistent, deterministic classification
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`OpenRouter API error ${response.status}: ${errorText}`);
  }

  const data = await response.json();
  const raw = data.choices[0].message.content.trim();

  // Strip markdown code fences if the model wrapped the JSON
  const cleaned = raw.replace(/```(?:json)?|```/g, "").trim();

  try {
    return JSON.parse(cleaned) as LLMIntentResult;
  } catch {
    console.warn("[intentClassifier] Failed to parse LLM JSON, raw response:", raw);
    // Graceful fallback — treat as partial so the user is shown the borderline UI
    return { verdict: "partial", reason: "Could not parse LLM response; treating as borderline." };
  }
}
