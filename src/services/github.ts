import { Octokit } from "@octokit/rest";

const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });
const OWNER = "wickyaf123";
const REPO = "agenticmvp-seo";

export async function commitContentFile(
  path: string,
  content: string,
  message: string
): Promise<boolean> {
  try {
    // Check if file already exists
    let sha: string | undefined;
    try {
      const existing = await octokit.repos.getContent({
        owner: OWNER,
        repo: REPO,
        path,
      });
      if (!Array.isArray(existing.data) && "sha" in existing.data) {
        sha = existing.data.sha;
      }
    } catch {
      // File doesn't exist yet, that's fine
    }

    await octokit.repos.createOrUpdateFileContents({
      owner: OWNER,
      repo: REPO,
      path,
      message,
      content: Buffer.from(content).toString("base64"),
      sha,
    });

    console.log(`[GitHub] Committed: ${path}`);
    return true;
  } catch (error) {
    console.error(`[GitHub] Failed to commit ${path}:`, error);
    return false;
  }
}

export async function listExistingContent(
  dir: string
): Promise<string[]> {
  try {
    const { data } = await octokit.repos.getContent({
      owner: OWNER,
      repo: REPO,
      path: dir,
    });

    if (Array.isArray(data)) {
      return data
        .filter((f) => f.name.endsWith(".json"))
        .map((f) => f.name.replace(".json", ""));
    }
    return [];
  } catch {
    return [];
  }
}

export async function triggerVercelDeploy(): Promise<boolean> {
  const hookUrl = process.env.VERCEL_DEPLOY_HOOK;
  if (!hookUrl) {
    console.warn("[Deploy] No VERCEL_DEPLOY_HOOK configured, skipping");
    return false;
  }

  try {
    const res = await fetch(hookUrl, { method: "POST" });
    console.log(`[Deploy] Vercel rebuild triggered: ${res.status}`);
    return res.ok;
  } catch (error) {
    console.error("[Deploy] Failed to trigger Vercel rebuild:", error);
    return false;
  }
}
