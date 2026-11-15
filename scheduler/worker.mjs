// Minute detector; video processing runs on GitHub only when work is pending.
const ROOT = "https://api.github.com/repos/ahmedmatwe/tiktok-agent";
export function accounts(env) {
  const names = [...new Set((env.TIKTOK_USERNAMES || "").split(/[,\s]+/)
    .filter(Boolean).map(n => n.replace(/^@/, "").toLowerCase()))];
  if (!names.length || names.some(n => !/^[a-z0-9._]{1,24}$/.test(n))) {
    throw new Error("Set TIKTOK_USERNAMES to valid usernames");
  }
  return names;
}
export async function dispatch(env, fetcher = fetch) {
  if (!env.GITHUB_TOKEN) throw new Error("Missing GITHUB_TOKEN secret");
  const names = accounts(env);
  const platforms = (env.TARGET_PLATFORMS || "youtube,instagram")
    .split(",").map(n => n.trim()).filter(Boolean);
  if (!platforms.length || platforms.some(p => !["youtube","instagram","telegram","facebook"].includes(p))) {
    throw new Error("Invalid TARGET_PLATFORMS");
  }
  const headers = {
    Authorization: "Bearer " + env.GITHUB_TOKEN,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "tiktok-agent-scheduler",
  };
  async function get(url, customHeaders = headers) {
    const r = await fetcher(url, { headers: customHeaders, signal: AbortSignal.timeout(15000) });
    if (!r.ok) throw new Error("Source request failed: HTTP " + r.status);
    return r;
  }
  const runs = await (await get(ROOT + "/actions/workflows/agent.yml/runs?branch=main&per_page=10")).json();
  if (!Array.isArray(runs.workflow_runs)) throw new Error("Invalid workflow run response");
  if (runs.workflow_runs.some(r => r.status !== "completed")) return "active";
  // Bound retries after a failed publishing run to avoid burning free quotas.
  const last = runs.workflow_runs[0];
  if (last?.conclusion === "failure" && Date.now() - Date.parse(last.updated_at) < 15 * 60000) {
    return "retry-cooldown";
  }
  const state = await (await get(ROOT + "/contents/data/state.json?ref=main",
    { ...headers, Accept: "application/vnd.github.raw+json" })).json();
  let pending = false;
  const failed = [];
  for (const [index, name] of names.entries()) {
    try {
      // Public page only. NEVER send GitHub credentials to TikTok.
      const page = await get("https://www.tiktok.com/embed/@" + name, {
        "User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache",
      });
      const html = await page.text();
      const ids = [...new Set([...html.matchAll(/\/video\/(\d{15,})/g)].map(m => m[1]))];
      if (!ids.length) throw new Error("No video IDs");
      const primary = (env.PRIMARY_USERNAME || names[0]).replace(/^@/, "").toLowerCase();
      const initialized = state["__initialized__:" + name] ||
        (name === primary && state.__initialized__);
      if (!initialized || ids.some(id => {
        const entry = state[id];
        return !entry || (!entry._skipped_on_first_run && (name === primary ? platforms : ["youtube", "instagram"]).some(p => !entry[p]));
      })) pending = true;
    } catch {
      failed.push(name);
    }
  }
  if (!pending) {
    if (failed.length) throw new Error("TikTok discovery failed for: " + failed.join(","));
    return "idle";
  }
  const sent = await fetcher(ROOT + "/actions/workflows/agent.yml/dispatches", {
    method: "POST", headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({ ref: "main", inputs: { probe: false } }),
    signal: AbortSignal.timeout(15000),
  });
  if (!sent.ok) throw new Error("Workflow dispatch failed: HTTP " + sent.status);
  console.log("Workflow dispatch accepted; unavailable sources: " + failed.join(","));
  return "dispatched";
}
export default {
  async scheduled(controller, env) { await dispatch(env); },
};
