import "dotenv/config";
import express from "express";
import cron from "node-cron";
import { runContentGeneration } from "./cron/content-generator.js";

const app = express();
const PORT = process.env.PORT || 3001;

app.use(express.json());

// Health check
app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
  });
});

// Manual trigger for content generation
app.post("/api/generate", async (_req, res) => {
  try {
    const result = await runContentGeneration();
    res.json({ success: true, ...result });
  } catch (error) {
    res.status(500).json({ error: String(error) });
  }
});

// Cron: Generate new SEO content every 48 hours
cron.schedule("0 */48 * * *", async () => {
  console.log("[CRON] Starting content generation...");
  try {
    const result = await runContentGeneration();
    console.log("[CRON] Content generation complete:", result);
  } catch (error) {
    console.error("[CRON] Content generation failed:", error);
  }
});

app.listen(PORT, () => {
  console.log(`AgenticMVP Backend running on port ${PORT}`);
  console.log("Cron: Content generation every 48 hours");
});
