import {
  generateSolutionContent,
  generateUseCaseContent,
  generateBlogContent,
} from "../services/gemini.js";
import {
  commitContentFile,
  listExistingContent,
  triggerVercelDeploy,
} from "../services/github.js";
import {
  SOLUTION_TOPICS,
  USE_CASE_TOPICS,
  BLOG_TOPICS,
} from "../config/keywords.js";

const BATCH_SIZE = 3; // Pages per run

async function getExistingSlugs() {
  const [solutions, useCases, agents] = await Promise.all([
    listExistingContent("content/solutions"),
    listExistingContent("content/use-cases"),
    listExistingContent("content/agents"),
  ]);
  return { solutions, useCases, agents };
}

function getNextTopics(
  existing: string[],
  topics: { slug: string }[],
  count: number
) {
  return topics.filter((t) => !existing.includes(t.slug)).slice(0, count);
}

export async function runContentGeneration() {
  console.log("[Generator] Starting content generation batch...");

  const existingSlugs = await getExistingSlugs();
  console.log(
    `[Generator] Existing: ${existingSlugs.solutions.length} solutions, ${existingSlugs.useCases.length} use-cases, ${existingSlugs.agents.length} agents`
  );

  let generated = 0;
  let failed = 0;

  // Pick next topics to generate (rotate between types)
  const nextSolutions = getNextTopics(
    existingSlugs.solutions,
    SOLUTION_TOPICS,
    1
  );
  const nextUseCases = getNextTopics(
    existingSlugs.useCases,
    USE_CASE_TOPICS,
    1
  );
  const nextBlogs = getNextTopics(
    await listExistingContent("content/blog"),
    BLOG_TOPICS,
    1
  );

  // Generate solution pages
  for (const topic of nextSolutions) {
    try {
      console.log(`[Generator] Creating solution: ${topic.industry}`);
      const json = await generateSolutionContent(
        topic.industry,
        topic.slug,
        existingSlugs
      );
      // Validate JSON
      JSON.parse(json);
      const success = await commitContentFile(
        `content/solutions/${topic.slug}.json`,
        json,
        `Add solution page: AI Agents for ${topic.industry}`
      );
      if (success) generated++;
      else failed++;
    } catch (error) {
      console.error(`[Generator] Failed solution ${topic.slug}:`, error);
      failed++;
    }
  }

  // Generate use case pages
  for (const topic of nextUseCases) {
    try {
      console.log(`[Generator] Creating use case: ${topic.functionName}`);
      const json = await generateUseCaseContent(
        topic.functionName,
        topic.slug,
        existingSlugs
      );
      JSON.parse(json);
      const success = await commitContentFile(
        `content/use-cases/${topic.slug}.json`,
        json,
        `Add use case page: AI ${topic.functionName} Automation`
      );
      if (success) generated++;
      else failed++;
    } catch (error) {
      console.error(`[Generator] Failed use case ${topic.slug}:`, error);
      failed++;
    }
  }

  // Generate blog posts
  for (const topic of nextBlogs) {
    try {
      console.log(`[Generator] Creating blog: ${topic.title}`);
      const json = await generateBlogContent(
        topic.title,
        topic.slug,
        existingSlugs
      );
      JSON.parse(json);
      const success = await commitContentFile(
        `content/blog/${topic.slug}.json`,
        json,
        `Add blog post: ${topic.title}`
      );
      if (success) generated++;
      else failed++;
    } catch (error) {
      console.error(`[Generator] Failed blog ${topic.slug}:`, error);
      failed++;
    }
  }

  // Trigger Vercel rebuild if we generated anything
  if (generated > 0) {
    await triggerVercelDeploy();
  }

  const result = {
    generated,
    failed,
    timestamp: new Date().toISOString(),
  };

  console.log(`[Generator] Done: ${generated} generated, ${failed} failed`);
  return result;
}

// Allow running directly: npx tsx src/cron/content-generator.ts
if (process.argv[1]?.includes("content-generator")) {
  runContentGeneration()
    .then((r) => console.log("Result:", r))
    .catch(console.error);
}
