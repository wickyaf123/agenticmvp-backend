import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, TypeVar

from app.config.keywords import BLOG_TOPICS, SOLUTION_TOPICS, USE_CASE_TOPICS
from app.services.claude import (
    generate_blog_content,
    generate_solution_content,
    generate_use_case_content,
)
from app.services.github_service import (
    commit_content_file,
    list_existing_content,
    trigger_vercel_deploy,
)
from app.services.supabase_client import upsert_content_item

logger = logging.getLogger(__name__)

BATCH_SIZE = 3

T = TypeVar("T", bound=dict)


def _persist_content(kind: str, slug: str, raw_json: str) -> None:
    try:
        parsed = json.loads(raw_json)
        title = (
            parsed.get("title")
            or parsed.get("metaTitle")
            or parsed.get("h1")
            or slug
        )
        meta_description = parsed.get("metaDescription") or parsed.get("description")
        upsert_content_item(
            {
                "type": kind,
                "slug": slug,
                "title": title,
                "metaDescription": meta_description,
                "data": parsed,
            }
        )
    except Exception as e:
        logger.error("[Generator] persist_content(%s/%s) failed: %s", kind, slug, e)


def _get_existing_slugs() -> Dict[str, List[str]]:
    return {
        "solutions": list_existing_content("content/solutions"),
        "useCases": list_existing_content("content/use-cases"),
        "agents": list_existing_content("content/agents"),
    }


def _get_next_topics(existing: List[str], topics: List[dict], count: int) -> List[dict]:
    return [t for t in topics if t["slug"] not in existing][:count]


def run_content_generation() -> dict:
    logger.info("[Generator] Starting content generation batch...")

    existing_slugs = _get_existing_slugs()
    logger.info(
        "[Generator] Existing: %d solutions, %d use-cases, %d agents",
        len(existing_slugs["solutions"]),
        len(existing_slugs["useCases"]),
        len(existing_slugs["agents"]),
    )

    generated = 0
    failed = 0

    next_solutions = _get_next_topics(existing_slugs["solutions"], SOLUTION_TOPICS, 1)
    next_use_cases = _get_next_topics(existing_slugs["useCases"], USE_CASE_TOPICS, 1)
    next_blogs = _get_next_topics(
        list_existing_content("content/blog"), BLOG_TOPICS, 1
    )

    for topic in next_solutions:
        try:
            logger.info("[Generator] Creating solution: %s", topic["industry"])
            raw = generate_solution_content(topic["industry"], topic["slug"], existing_slugs)
            json.loads(raw)  # validate
            success = commit_content_file(
                f"content/solutions/{topic['slug']}.json",
                raw,
                f"Add solution page: AI Agents for {topic['industry']}",
            )
            if success:
                generated += 1
                _persist_content("solution", topic["slug"], raw)
            else:
                failed += 1
        except Exception as e:
            logger.error("[Generator] Failed solution %s: %s", topic["slug"], e)
            failed += 1

    for topic in next_use_cases:
        try:
            logger.info("[Generator] Creating use case: %s", topic["functionName"])
            raw = generate_use_case_content(topic["functionName"], topic["slug"], existing_slugs)
            json.loads(raw)
            success = commit_content_file(
                f"content/use-cases/{topic['slug']}.json",
                raw,
                f"Add use case page: AI {topic['functionName']} Automation",
            )
            if success:
                generated += 1
                _persist_content("use_case", topic["slug"], raw)
            else:
                failed += 1
        except Exception as e:
            logger.error("[Generator] Failed use case %s: %s", topic["slug"], e)
            failed += 1

    for topic in next_blogs:
        try:
            logger.info("[Generator] Creating blog: %s", topic["title"])
            raw = generate_blog_content(topic["title"], topic["slug"], existing_slugs)
            json.loads(raw)
            success = commit_content_file(
                f"content/blog/{topic['slug']}.json",
                raw,
                f"Add blog post: {topic['title']}",
            )
            if success:
                generated += 1
                _persist_content("blog_post", topic["slug"], raw)
            else:
                failed += 1
        except Exception as e:
            logger.error("[Generator] Failed blog %s: %s", topic["slug"], e)
            failed += 1

    if generated > 0:
        trigger_vercel_deploy()

    result = {
        "generated": generated,
        "failed": failed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("[Generator] Done: %d generated, %d failed", generated, failed)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Result:", run_content_generation())
