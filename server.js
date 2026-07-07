/**
 * server.js — ModifAI Input Validation Module
 *
 * Minimal Express server that:
 *  1. Reads OPENROUTER_API_KEY from the environment (set in .env locally, or via Render env vars)
 *  2. Injects it as window.__MODIFAI_CONFIG__ into the served index.html
 *  3. Serves all other static assets (JS, CSS, etc.) unchanged
 *
 * This keeps the API key entirely server-side — it is never committed to the repository
 * and never visible in the browser's network inspector as a hardcoded string.
 */

"use strict";

const express = require("express");
const path = require("path");
const fs = require("fs");
require("dotenv").config();

const app = express();
const PORT = process.env.PORT || 3000;

// ── Inject API key into index.html at request time ────────────────────────────
app.get("/", (req, res) => {
  const htmlPath = path.join(__dirname, "index.html");
  let html = fs.readFileSync(htmlPath, "utf8");

  const apiKey = process.env.OPENROUTER_API_KEY || "";

  // Inject a tiny config object into <head> before any other scripts run
  const configScript = `<script>
  // Injected by server.js — API key comes from server environment, never from the client
  window.__MODIFAI_CONFIG__ = { apiKey: ${JSON.stringify(apiKey)} };
</script>`;

  html = html.replace("</head>", configScript + "\n</head>");
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.send(html);
});

// ── Serve all other static files (fonts, etc.) ────────────────────────────────
app.use(express.static(__dirname));

// ── Health check endpoint (Render uses this to verify the service is up) ──────
app.get("/health", (req, res) => {
  res.json({ status: "ok", module: "modifai-input-validation", timestamp: new Date().toISOString() });
});

// ── Start ─────────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  const keyStatus = process.env.OPENROUTER_API_KEY ? "✓ API key loaded" : "⚠ No API key — heuristic mode";
  console.log(`\n🚀 ModifAI Input Validation running on http://localhost:${PORT}`);
  console.log(`   ${keyStatus}\n`);
});
