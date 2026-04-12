import { GoogleGenerativeAI } from "@google/generative-ai";

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY || "");

export async function generateSolutionContent(
  industry: string,
  slug: string,
  existingSlugs: { solutions: string[]; useCases: string[]; agents: string[] }
): Promise<string> {
  const model = genAI.getGenerativeModel({ model: "gemini-2.0-flash" });

  const prompt = `Generate a JSON object for an AI agency website page about "AI Agents for ${industry}".

The JSON must match this exact structure:
{
  "slug": "${slug}",
  "industry": "${industry}",
  "title": "AI Agents for ${industry}: [compelling subtitle with specific benefit]",
  "metaDescription": "[150-160 chars, must include 'AI agents' and '${industry}']",
  "heroSubtitle": "[1-2 sentences with a quantified benefit, e.g., 'Reduce costs by 60%']",
  "painPoints": [
    { "title": "[specific problem]", "description": "[2-3 sentences explaining the problem with data]" },
    { "title": "...", "description": "..." },
    { "title": "...", "description": "..." },
    { "title": "...", "description": "..." }
  ],
  "solutions": [
    { "title": "[how AI agents solve pain point 1]", "description": "[2-3 sentences]" },
    { "title": "...", "description": "..." },
    { "title": "...", "description": "..." },
    { "title": "...", "description": "..." }
  ],
  "useCases": ${JSON.stringify(existingSlugs.useCases.slice(0, 4))},
  "agentTypes": ${JSON.stringify(existingSlugs.agents.slice(0, 3))},
  "stats": [
    { "label": "[metric name]", "value": "[realistic number with % or unit]" },
    { "label": "...", "value": "..." },
    { "label": "...", "value": "..." },
    { "label": "...", "value": "..." }
  ],
  "faqs": [
    { "question": "How much do AI agents cost for ${industry}?", "answer": "[detailed 3-4 sentence answer]" },
    { "question": "[long-tail keyword question]", "answer": "[detailed answer]" },
    { "question": "[long-tail keyword question]", "answer": "[detailed answer]" },
    { "question": "[long-tail keyword question]", "answer": "[detailed answer]" },
    { "question": "[long-tail keyword question]", "answer": "[detailed answer]" }
  ],
  "relatedSolutions": ${JSON.stringify(existingSlugs.solutions.slice(0, 4))}
}

Rules:
- Pain points must be REAL problems specific to ${industry}, not generic
- Stats must be realistic industry benchmarks
- FAQs must target long-tail search keywords
- metaDescription must be exactly 150-160 characters
- Return ONLY valid JSON, no markdown, no code fences`;

  const result = await model.generateContent(prompt);
  const text = result.response.text();
  // Strip any markdown code fences
  return text.replace(/```json\n?/g, "").replace(/```\n?/g, "").trim();
}

export async function generateUseCaseContent(
  functionName: string,
  slug: string,
  existingSlugs: { solutions: string[]; useCases: string[]; agents: string[] }
): Promise<string> {
  const model = genAI.getGenerativeModel({ model: "gemini-2.0-flash" });

  const prompt = `Generate a JSON object for an AI agency website page about "AI ${functionName} Automation".

The JSON must match this exact structure:
{
  "slug": "${slug}",
  "function": "${functionName}",
  "title": "AI ${functionName} Automation",
  "metaDescription": "[150-160 chars, must include 'AI' and '${functionName}']",
  "heroSubtitle": "[1-2 sentences with a specific benefit]",
  "beforeAfter": {
    "before": "[3-4 sentences describing the manual process and its problems]",
    "after": "[3-4 sentences describing how AI agents transform this process]"
  },
  "features": [
    { "title": "[capability]", "description": "[2-3 sentences]" },
    { "title": "...", "description": "..." },
    { "title": "...", "description": "..." },
    { "title": "...", "description": "..." }
  ],
  "industries": ${JSON.stringify(existingSlugs.solutions.slice(0, 4))},
  "agentTypes": ${JSON.stringify(existingSlugs.agents.slice(0, 3))},
  "stats": [
    { "label": "[metric]", "value": "[number]" },
    { "label": "...", "value": "..." },
    { "label": "...", "value": "..." },
    { "label": "...", "value": "..." }
  ],
  "faqs": [
    { "question": "[long-tail keyword question about ${functionName} automation]", "answer": "[detailed answer]" },
    { "question": "...", "answer": "..." },
    { "question": "...", "answer": "..." },
    { "question": "...", "answer": "..." }
  ],
  "relatedUseCases": ${JSON.stringify(existingSlugs.useCases.slice(0, 3))}
}

Return ONLY valid JSON, no markdown, no code fences.`;

  const result = await model.generateContent(prompt);
  const text = result.response.text();
  return text.replace(/```json\n?/g, "").replace(/```\n?/g, "").trim();
}

export async function generateBlogContent(
  topic: string,
  slug: string,
  existingSlugs: { solutions: string[]; useCases: string[]; agents: string[] }
): Promise<string> {
  const model = genAI.getGenerativeModel({ model: "gemini-2.0-flash" });

  const prompt = `Generate a JSON object for a blog post about "${topic}" for an AI agency that builds AI agents.

The JSON must match this exact structure:
{
  "slug": "${slug}",
  "title": "${topic}",
  "metaDescription": "[150-160 chars, SEO-optimized]",
  "date": "${new Date().toISOString().split("T")[0]}",
  "author": "AgenticMVP Team",
  "category": "[one of: AI Fundamentals, Business, Guide, Comparison, SEO, Industry]",
  "content": "[Full article with ## and ### headings, 800-1200 words, separated by double newlines]",
  "relatedSolutions": ${JSON.stringify(existingSlugs.solutions.slice(0, 3))},
  "relatedUseCases": ${JSON.stringify(existingSlugs.useCases.slice(0, 2))},
  "relatedAgents": ${JSON.stringify(existingSlugs.agents.slice(0, 2))}
}

The content should be genuinely informative, not marketing fluff.
Return ONLY valid JSON, no markdown, no code fences.`;

  const result = await model.generateContent(prompt);
  const text = result.response.text();
  return text.replace(/```json\n?/g, "").replace(/```\n?/g, "").trim();
}
