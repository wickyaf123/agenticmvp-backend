import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from resend import Emails
import resend

from app.api.runs import router as runs_router
from app.cron.content_generator import run_content_generation
from app.orchestrator.checkpointer import bootstrap_checkpointer
from app.services.supabase_client import insert_lead

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

resend.api_key = os.getenv("RESEND_API_KEY")

_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bootstrap LangGraph Postgres checkpointer (idempotent migrations).
    if os.getenv("ORCHESTRATOR_PG_DSN"):
        try:
            await bootstrap_checkpointer()
            logger.info("Orchestrator checkpointer ready.")
        except Exception as exc:  # noqa: BLE001
            logger.error("Checkpointer bootstrap failed: %s", exc)
    else:
        logger.warning(
            "ORCHESTRATOR_PG_DSN unset — orchestrator runs will fail until configured."
        )

    # NOTE: APScheduler retired. Recurring content generation will be
    # re-enabled as an RQ scheduled job in Phase 1.
    logger.info("AgenticMVP Backend started (orchestrator mode).")
    yield
    logger.info("AgenticMVP Backend shutting down.")


app = FastAPI(title="AgenticMVP Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://agenticmvp.dev",
        "https://www.agenticmvp.dev",
        "https://agenticmvp.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(runs_router)


class OnboardPayload(BaseModel):
    name: str
    email: EmailStr
    projectIdea: Optional[str] = None
    budget: Optional[str] = None
    stage: Optional[str] = None
    timeline: Optional[str] = None
    source: Optional[str] = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "uptime": time.time() - _start_time,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "orchestrator_configured": bool(os.getenv("ORCHESTRATOR_PG_DSN")),
    }


def _persist_lead_bg(payload: OnboardPayload) -> None:
    try:
        result = insert_lead(payload.model_dump())
        if result.get("id"):
            logger.info("[ONBOARD] Lead persisted: %s", result["id"])
    except Exception as e:
        logger.error("[ONBOARD] Lead persist failed: %s", e)


@app.post("/api/onboard")
def onboard(payload: OnboardPayload, background_tasks: BackgroundTasks):
    try:
        name = payload.name
        email = payload.email
        source = payload.source or "Website"

        Emails.send(
            {
                "from": "AgenticMVP <onboarding@agenticmvp.dev>",
                "to": ["team@agenticmvp.dev"],
                "subject": f"New Lead: {name} — {source}",
                "html": f"""
        <h2>New Onboarding Submission</h2>
        <table style="border-collapse:collapse;width:100%;max-width:600px">
          <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold">Name</td><td style="padding:8px;border:1px solid #ddd">{name}</td></tr>
          <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold">Email</td><td style="padding:8px;border:1px solid #ddd">{email}</td></tr>
          <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold">Project Idea</td><td style="padding:8px;border:1px solid #ddd">{payload.projectIdea or '—'}</td></tr>
          <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold">Budget</td><td style="padding:8px;border:1px solid #ddd">{payload.budget or '—'}</td></tr>
          <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold">Stage</td><td style="padding:8px;border:1px solid #ddd">{payload.stage or '—'}</td></tr>
          <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold">Timeline</td><td style="padding:8px;border:1px solid #ddd">{payload.timeline or '—'}</td></tr>
          <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold">Source Button</td><td style="padding:8px;border:1px solid #ddd">{source}</td></tr>
        </table>
        <p style="margin-top:16px;color:#666">Submitted at {datetime.now(timezone.utc).isoformat()}</p>
                """,
            }
        )

        Emails.send(
            {
                "from": "AgenticMVP <hello@agenticmvp.dev>",
                "to": [email],
                "subject": "We got your submission — let's build!",
                "html": f"""
        <div style="font-family:sans-serif;max-width:600px">
          <h2 style="color:#ff4d00">Hey {name}!</h2>
          <p>Thanks for reaching out. We've received your project details and our team will review them shortly.</p>
          <p>In the meantime, feel free to book a strategy call so we can dive deeper:</p>
          <a href="https://cal.com/himanshu-sanwal-qb4dls/30min" style="display:inline-block;background:#ff4d00;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;margin-top:8px">Book a Call →</a>
          <p style="margin-top:24px;color:#999">— The AgenticMVP Team</p>
        </div>
                """,
            }
        )

        background_tasks.add_task(_persist_lead_bg, payload)
        return {"success": True, "message": "Submission received"}
    except Exception as e:
        logger.error("[ONBOARD] Error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to process submission")


@app.post("/api/generate")
def generate():
    """Manual content generation trigger (kept until Phase 1 wraps it as a graph)."""
    try:
        result = run_content_generation()
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
