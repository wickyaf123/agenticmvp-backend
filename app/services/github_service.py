import base64
import logging
import os
from typing import List

import httpx
from github import Github, GithubException
from github.ContentFile import ContentFile

logger = logging.getLogger(__name__)

_gh = Github(os.getenv("GITHUB_TOKEN"))
OWNER = "wickyaf123"
REPO = "agenticmvp-seo"


def _repo():
    return _gh.get_repo(f"{OWNER}/{REPO}")


def commit_content_file(path: str, content: str, message: str) -> bool:
    """Create or update a file on the default branch."""
    try:
        repo = _repo()
        sha = None
        try:
            existing = repo.get_contents(path)
            if isinstance(existing, list):
                sha = None
            else:
                sha = existing.sha
        except GithubException:
            sha = None

        if sha:
            repo.update_file(path=path, message=message, content=content, sha=sha)
        else:
            repo.create_file(path=path, message=message, content=content)

        logger.info("[GitHub] Committed: %s", path)
        return True
    except Exception as e:
        logger.error("[GitHub] Failed to commit %s: %s", path, e)
        return False


def list_existing_content(directory: str) -> List[str]:
    try:
        repo = _repo()
        data = repo.get_contents(directory)
        if not isinstance(data, list):
            return []
        return [f.name.replace(".json", "") for f in data if f.name.endswith(".json")]
    except Exception:
        return []


def trigger_vercel_deploy() -> bool:
    hook_url = os.getenv("VERCEL_DEPLOY_HOOK")
    if not hook_url:
        logger.warning("[Deploy] No VERCEL_DEPLOY_HOOK configured, skipping")
        return False
    try:
        res = httpx.post(hook_url, timeout=30)
        logger.info("[Deploy] Vercel rebuild triggered: %s", res.status_code)
        return res.is_success
    except Exception as e:
        logger.error("[Deploy] Failed to trigger Vercel rebuild: %s", e)
        return False
