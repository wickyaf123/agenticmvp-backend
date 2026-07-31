"""
Claude-backed content generation (replaces the former Gemini service).

Same public surface as the old `gemini.py` — `generate_solution_content`,
`generate_use_case_content`, `generate_blog_content` — each returning a
fence-stripped JSON string, so `app/cron/content_generator.py` is unchanged.

Blog prose additionally runs through a humanization pass (`humanize_text`) that
rewrites the article to read like a person wrote it, not an LLM.

Env:
    ANTHROPIC_API_KEY   required
    ANTHROPIC_MODEL     model id (default 'claude-sonnet-5'; 'claude-haiku-4-5' for cheaper/faster)
    ANTHROPIC_HUMANIZE  '1' (default) to run the de-AI pass on blog content, '0' to skip
"""

import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List

import anthropic

_client = None
_FENCE_RE = re.compile(r"```(?:json)?\n?|```\n?")

_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
_MAX_TOKENS = 8000

# JSON-only system prompt: Sonnet 5 supports structured prompting well, but we keep
# the fence-strip as a belt-and-suspenders guard in case a stray fence slips through.
_JSON_SYSTEM = (
    "You are a JSON generation API. Output only a single valid JSON object that "
    "matches the requested structure exactly. No prose, no markdown, no code fences."
)

# The humanization contract. Deliberately concrete about the tells to remove — vague
# instructions ("make it human") don't move the needle.
_HUMANIZE_SYSTEM = """You rewrite AI-generated articles so they read as if written by an experienced human practitioner, not a language model. Rewrite the text you are given.

Keep:
- The meaning, facts, and any specific numbers or claims — do not invent new ones.
- All Markdown structure: the same ## and ### headings, lists, and rough section order.
- Roughly the same length (within ~10%).

Fix the AI tells:
- Cut throat-clearing and filler openers ("In today's fast-paced world", "It's important to note that", "In this article we will", "Let's dive in").
- Kill the closing "In conclusion" / "In summary" wrap-up unless a real conclusion adds something.
- Vary sentence length and rhythm hard — mix short punchy sentences with longer ones. AI writes in a uniform mid-length cadence; humans don't.
- Break up the relentless "Firstly / Moreover / Furthermore / Additionally" connective tissue. Use them sparingly or not at all.
- Drop hype/filler vocabulary: leverage, harness, unlock, robust, seamless, game-changer, revolutionize, elevate, delve, tapestry, landscape, realm, testament, navigate the complexities.
- Prefer concrete specifics and plain verbs over abstraction. Contractions are fine.
- Don't make every paragraph the same shape or length. Let some breathe, keep some tight.

Output only the rewritten article body in Markdown. No preamble, no explanation, no code fences."""


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _message(prompt: str, system: str, max_tokens: int = _MAX_TOKENS) -> str:
    """Single-shot Claude call. Thinking disabled — these are generation tasks, not
    reasoning tasks, and we don't want thinking eating the token budget."""
    response = _get_client().messages.create(
        model=_MODEL,
        max_tokens=max_tokens,
        thinking={"type": "disabled"},
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")
    return text.strip()


def _generate(prompt: str) -> str:
    """Generate a JSON payload and strip any stray code fences."""
    return _FENCE_RE.sub("", _message(prompt, _JSON_SYSTEM)).strip()


def humanize_text(text: str) -> str:
    """Rewrite article prose to read like a human wrote it. Best-effort: on any
    failure, return the original text unchanged so generation never hard-fails here."""
    if not text or not text.strip():
        return text
    try:
        rewritten = _message(text, _HUMANIZE_SYSTEM)
        rewritten = _FENCE_RE.sub("", rewritten).strip()
        return rewritten or text
    except Exception:
        return text


def generate_solution_content(
    industry: str, slug: str, existing_slugs: Dict[str, List[str]]
) -> str:
    use_cases = json.dumps(existing_slugs["useCases"][:4])
    agents = json.dumps(existing_slugs["agents"][:3])
    solutions = json.dumps(existing_slugs["solutions"][:4])

    prompt = f"""Generate a JSON object for an AI agency website page about "AI Agents for {industry}".

The JSON must match this exact structure:
{{
  "slug": "{slug}",
  "industry": "{industry}",
  "title": "AI Agents for {industry}: [compelling subtitle with specific benefit]",
  "metaDescription": "[150-160 chars, must include 'AI agents' and '{industry}']",
  "heroSubtitle": "[1-2 sentences with a quantified benefit, e.g., 'Reduce costs by 60%']",
  "painPoints": [
    {{ "title": "[specific problem]", "description": "[2-3 sentences explaining the problem with data]" }},
    {{ "title": "...", "description": "..." }},
    {{ "title": "...", "description": "..." }},
    {{ "title": "...", "description": "..." }}
  ],
  "solutions": [
    {{ "title": "[how AI agents solve pain point 1]", "description": "[2-3 sentences]" }},
    {{ "title": "...", "description": "..." }},
    {{ "title": "...", "description": "..." }},
    {{ "title": "...", "description": "..." }}
  ],
  "useCases": {use_cases},
  "agentTypes": {agents},
  "stats": [
    {{ "label": "[metric name]", "value": "[realistic number with % or unit]" }},
    {{ "label": "...", "value": "..." }},
    {{ "label": "...", "value": "..." }},
    {{ "label": "...", "value": "..." }}
  ],
  "faqs": [
    {{ "question": "How much do AI agents cost for {industry}?", "answer": "[detailed 3-4 sentence answer]" }},
    {{ "question": "[long-tail keyword question]", "answer": "[detailed answer]" }},
    {{ "question": "[long-tail keyword question]", "answer": "[detailed answer]" }},
    {{ "question": "[long-tail keyword question]", "answer": "[detailed answer]" }},
    {{ "question": "[long-tail keyword question]", "answer": "[detailed answer]" }}
  ],
  "relatedSolutions": {solutions}
}}

Rules:
- Pain points must be REAL problems specific to {industry}, not generic
- Stats must be realistic industry benchmarks
- FAQs must target long-tail search keywords
- metaDescription must be exactly 150-160 characters
- Return ONLY valid JSON, no markdown, no code fences"""

    return _generate(prompt)


def generate_use_case_content(
    function_name: str, slug: str, existing_slugs: Dict[str, List[str]]
) -> str:
    industries = json.dumps(existing_slugs["solutions"][:4])
    agents = json.dumps(existing_slugs["agents"][:3])
    related = json.dumps(existing_slugs["useCases"][:3])

    prompt = f"""Generate a JSON object for an AI agency website page about "AI {function_name} Automation".

The JSON must match this exact structure:
{{
  "slug": "{slug}",
  "function": "{function_name}",
  "title": "AI {function_name} Automation",
  "metaDescription": "[150-160 chars, must include 'AI' and '{function_name}']",
  "heroSubtitle": "[1-2 sentences with a specific benefit]",
  "beforeAfter": {{
    "before": "[3-4 sentences describing the manual process and its problems]",
    "after": "[3-4 sentences describing how AI agents transform this process]"
  }},
  "features": [
    {{ "title": "[capability]", "description": "[2-3 sentences]" }},
    {{ "title": "...", "description": "..." }},
    {{ "title": "...", "description": "..." }},
    {{ "title": "...", "description": "..." }}
  ],
  "industries": {industries},
  "agentTypes": {agents},
  "stats": [
    {{ "label": "[metric]", "value": "[number]" }},
    {{ "label": "...", "value": "..." }},
    {{ "label": "...", "value": "..." }},
    {{ "label": "...", "value": "..." }}
  ],
  "faqs": [
    {{ "question": "[long-tail keyword question about {function_name} automation]", "answer": "[detailed answer]" }},
    {{ "question": "...", "answer": "..." }},
    {{ "question": "...", "answer": "..." }},
    {{ "question": "...", "answer": "..." }}
  ],
  "relatedUseCases": {related}
}}

Return ONLY valid JSON, no markdown, no code fences."""

    return _generate(prompt)


def generate_blog_content(
    topic: str, slug: str, existing_slugs: Dict[str, List[str]]
) -> str:
    related_solutions = json.dumps(existing_slugs["solutions"][:3])
    related_use_cases = json.dumps(existing_slugs["useCases"][:2])
    related_agents = json.dumps(existing_slugs["agents"][:2])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prompt = f"""Generate a JSON object for a blog post about "{topic}" for an AI agency that builds AI agents.

The JSON must match this exact structure:
{{
  "slug": "{slug}",
  "title": "{topic}",
  "metaDescription": "[150-160 chars, SEO-optimized]",
  "date": "{today}",
  "author": "AgenticMVP Team",
  "category": "[one of: AI Fundamentals, Business, Guide, Comparison, SEO, Industry]",
  "content": "[Full article with ## and ### headings, 800-1200 words, separated by double newlines]",
  "relatedSolutions": {related_solutions},
  "relatedUseCases": {related_use_cases},
  "relatedAgents": {related_agents}
}}

The content should be genuinely informative, not marketing fluff.
Return ONLY valid JSON, no markdown, no code fences."""

    raw = _generate(prompt)

    # Humanize the article body so it doesn't read as AI-generated. If anything about
    # parsing or the rewrite fails, fall back to the original JSON untouched.
    if os.getenv("ANTHROPIC_HUMANIZE", "1") != "0":
        try:
            parsed = json.loads(raw)
            body = parsed.get("content")
            if isinstance(body, str) and body.strip():
                parsed["content"] = humanize_text(body)
                raw = json.dumps(parsed, ensure_ascii=False)
        except Exception:
            pass

    return raw
