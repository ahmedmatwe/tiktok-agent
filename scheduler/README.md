# Timer (Cloudflare Worker)

Deployed as `tiktok-agent-scheduler`. Every 10 minutes it starts the `agent.yml`
GitHub run, unless a run is already going or the last one failed under 15
minutes ago. GitHub's own `schedule` trigger stays on as a slow fallback (it is
often delayed by hours).

It talks only to the GitHub API and never reads the posting history, which lives
in the private `tiktok-agent-data` repo. The agent decides what is new and posts
at most one new video per half hour.

Deploy: Actions → "Deploy minute detector to Cloudflare" → Run workflow.
Needs the `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` and
`SCHEDULER_GITHUB_TOKEN` secrets. Tests: `node --test scheduler/worker.test.mjs`.
