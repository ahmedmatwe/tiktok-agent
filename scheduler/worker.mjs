// Timer: starts the GitHub agent run every 10 minutes. The repo is public, so GitHub runs are free;
// the agent itself decides what is new and keeps one new video per half hour.
// Posting history lives in a private repo the Worker cannot (and need not) read.
const ROOT = "https://api.github.com/repos/ahmedmatwe/tiktok-agent";

export async function dispatch(env, fetcher = fetch) {
  if (!env.GITHUB_TOKEN) throw new Error("Missing GITHUB_TOKEN secret");
  const headers = {
    Authorization: "Bearer " + env.GITHUB_TOKEN,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "tiktok-agent-scheduler",
  };
  const r = await fetcher(ROOT + "/actions/workflows/agent.yml/runs?branch=main&per_page=5",
    { headers, signal: AbortSignal.timeout(15000) });
  if (!r.ok) throw new Error("GitHub runs request failed: HTTP " + r.status);
  const runs = (await r.json()).workflow_runs;
  if (!Array.isArray(runs)) throw new Error("Invalid workflow run response");
  if (runs.some(run => run.status !== "completed")) return "active";
  // After a failed run wait 15 minutes, so a broken platform is not hammered.
  const last = runs[0];
  if (last?.conclusion === "failure" && Date.now() - Date.parse(last.updated_at) < 15 * 60000) {
    return "retry-cooldown";
  }
  const sent = await fetcher(ROOT + "/actions/workflows/agent.yml/dispatches", {
    method: "POST", headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({ ref: "main", inputs: { probe: false } }),
    signal: AbortSignal.timeout(15000),
  });
  if (!sent.ok) throw new Error("Workflow dispatch failed: HTTP " + sent.status);
  return "dispatched";
}

export default {
  async scheduled(controller, env) { console.log(await dispatch(env)); },
};
