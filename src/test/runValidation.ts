/**
 * src/test/runValidation.ts
 * CLI test runner — validates a local PDF against a given intent.
 *
 * Usage:
 *   npx ts-node src/test/runValidation.ts <path-to-pdf> "<user intent>"
 *
 * Example:
 *   npx ts-node src/test/runValidation.ts test-documents/text-native-sample.pdf "HR policy assistant"
 */

import * as fs from "fs";
import * as path from "path";
import * as dotenv from "dotenv";
import { validateUpload } from "../orchestrator";

dotenv.config();

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error("Usage: npx ts-node src/test/runValidation.ts <pdf-path> \"<user intent>\"");
    process.exit(1);
  }

  const pdfPath = path.resolve(args[0]);
  const userIntent = args[1];
  const apiKey = process.env.OPENROUTER_API_KEY ?? "";

  if (!fs.existsSync(pdfPath)) {
    console.error(`File not found: ${pdfPath}`);
    process.exit(1);
  }

  if (!apiKey) {
    console.warn("⚠ OPENROUTER_API_KEY not set. LLM calls disabled; heuristic scoring will be used.");
  }

  console.log(`\n🔍 ModifAI Input Validation`);
  console.log(`📄 PDF: ${pdfPath}`);
  console.log(`🎯 Intent: "${userIntent}"`);
  console.log(`🔑 API Key: ${apiKey ? "✓ set" : "✗ not set"}\n`);
  console.log("─".repeat(60));

  const fileBuffer = new Uint8Array(fs.readFileSync(pdfPath));

  try {
    const result = await validateUpload(fileBuffer, userIntent, apiKey, (event) => {
      const pct = event.progress !== undefined ? `[${String(event.progress).padStart(3)}%]` : "      ";
      console.log(`${pct} [${event.stage}] ${event.message}`);
      if (event.detail) console.log(`       → ${event.detail}`);
    });

    console.log("\n" + "─".repeat(60));
    console.log("📊 RESULTS");
    console.log("─".repeat(60));
    console.log(`Final Quality Score : ${result.finalScore.toFixed(1)} / 100`);
    console.log(`Intent Verdict      : ${result.intentVerdict} (similarity: ${result.intentSimilarity.toFixed(3)})`);
    console.log(`Decision            : ${result.decision.toUpperCase()}`);
    console.log(`Reason              : ${result.reason}`);
    console.log("\n📄 Page Breakdown:");
    console.log(`  Total   : ${result.pageBreakdown.total}`);
    console.log(`  Text-native : ${result.pageBreakdown.textNative}`);
    console.log(`  Image-only  : ${result.pageBreakdown.imageOnly}`);
    console.log(`  Mixed       : ${result.pageBreakdown.mixed}`);
    console.log(`\n⏱  Timings (ms):`);
    console.log(`  PDF load      : ${result.timings.pdfLoad.toFixed(0)}`);
    console.log(`  OCR           : ${result.timings.ocr.toFixed(0)}`);
    console.log(`  Chunking      : ${result.timings.chunking.toFixed(0)}`);
    console.log(`  Intent check  : ${result.timings.intentCheck.toFixed(0)}`);
    console.log(`  Quality score : ${result.timings.qualityScoring.toFixed(0)}`);
    console.log(`  TOTAL         : ${result.timings.total.toFixed(0)}`);

    console.log("\n✅ Chunk Scores:");
    for (const sc of result.scoredChunks) {
      const conf = (sc.extractionConfidence * 100).toFixed(0);
      console.log(`  ${sc.chunkId.padEnd(14)} quality=${sc.qualityScore.padStart ? sc.qualityScore : sc.qualityScore}  confidence=${conf}%`);
    }

    console.log("\n" + "─".repeat(60));
    const emoji = result.decision === "proceed" ? "✅" : result.decision === "confirm-with-user" ? "⚠️" : "❌";
    console.log(`${emoji} Final Decision: ${result.decision}`);
    console.log("─".repeat(60) + "\n");

  } catch (err) {
    console.error("\n❌ Validation failed with error:", err);
    process.exit(1);
  }
}

main();
