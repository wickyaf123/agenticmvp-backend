import "dotenv/config";
import express from "express";
import cron from "node-cron";
import { Resend } from "resend";
import { runContentGeneration } from "./cron/content-generator.js";

const app = express();
const PORT = process.env.PORT || 3001;
const resend = new Resend(process.env.RESEND_API_KEY);

app.use(express.json());

// CORS — allow frontend origins
app.use((_req, res, next) => {
  const allowedOrigins = [
    "https://agenticmvpasap.io",
    "https://www.agenticmvpasap.io",
    "https://agenticmvp.vercel.app",
    "http://localhost:3000",
    "http://localhost:3001",
  ];
  const origin = _req.headers.origin;
  if (origin && allowedOrigins.includes(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
  }
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (_req.method === "OPTIONS") {
    res.status(204).end();
    return;
  }
  next();
});

// Health check
app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
  });
});

// Onboarding form submission
app.post("/api/onboard", async (req, res) => {
  try {
    const { name, email, projectIdea, budget, stage, timeline, source } = req.body;

    if (!name || !email) {
      res.status(400).json({ error: "Name and email are required" });
      return;
    }

    // Send notification email via Resend
    await resend.emails.send({
      from: "AgenticMVP <onboarding@agenticmvpasap.io>",
      to: ["TEAM@AGENTICMVPASAP.IO"],
      subject: `New Lead: ${name} — ${source || "Website"}`,
      html: `
        <h2>New Onboarding Submission</h2>
        <table style="border-collapse:collapse;width:100%;max-width:600px">
          <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold">Name</td><td style="padding:8px;border:1px solid #ddd">${name}</td></tr>
          <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold">Email</td><td style="padding:8px;border:1px solid #ddd">${email}</td></tr>
          <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold">Project Idea</td><td style="padding:8px;border:1px solid #ddd">${projectIdea || "—"}</td></tr>
          <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold">Budget</td><td style="padding:8px;border:1px solid #ddd">${budget || "—"}</td></tr>
          <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold">Stage</td><td style="padding:8px;border:1px solid #ddd">${stage || "—"}</td></tr>
          <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold">Timeline</td><td style="padding:8px;border:1px solid #ddd">${timeline || "—"}</td></tr>
          <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold">Source Button</td><td style="padding:8px;border:1px solid #ddd">${source || "—"}</td></tr>
        </table>
        <p style="margin-top:16px;color:#666">Submitted at ${new Date().toISOString()}</p>
      `,
    });

    // Send confirmation email to user
    await resend.emails.send({
      from: "AgenticMVP <hello@agenticmvpasap.io>",
      to: [email],
      subject: "We got your submission — let's build!",
      html: `
        <div style="font-family:sans-serif;max-width:600px">
          <h2 style="color:#ff4d00">Hey ${name}!</h2>
          <p>Thanks for reaching out. We've received your project details and our team will review them shortly.</p>
          <p>In the meantime, feel free to book a strategy call so we can dive deeper:</p>
          <a href="https://cal.com/himanshu-sanwal-qb4dls/30min" style="display:inline-block;background:#ff4d00;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;margin-top:8px">Book a Call →</a>
          <p style="margin-top:24px;color:#999">— The AgenticMVP Team</p>
        </div>
      `,
    });

    res.json({ success: true, message: "Submission received" });
  } catch (error) {
    console.error("[ONBOARD] Error:", error);
    res.status(500).json({ error: "Failed to process submission" });
  }
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
