# Minute detector and multiple sources — NOT DEPLOYED

Code is prepared and tested with mocked network responses. No Cloudflare Worker
has been deployed. Cloudflare sign-in currently blocks activation. GitHub's
existing half-hour schedule remains the live fallback.

## Source configuration
TIKTOK_USERNAME remains the original/primary account. Set TIKTOK_USERNAMES in
GitHub Secrets to comma-separated usernames, including the primary account.
All sources currently share the configured Instagram and YouTube destinations.
Separate destination accounts are not configured by this change.
TIKTOK_SEC_UID applies only to the primary account, never to secondary sources.

Each new source is baselined on its first successful check: existing videos are
skipped unless BACKFILL=true. Existing primary state is migrated without
skipping pending uploads. The first baseline check must finish before uploading
a new test video. Per-platform results are retained on failure. Failed
publishers now cause a failed run rather than a misleading green result.

## Detector
Worker cron is every minute. It reads repository state and public TikTok embed
pages, then dispatches GitHub only for an uninitialized source or a video with
missing target results. Idle checks do not start GitHub runners or Apify jobs.
It never forwards GitHub credentials to TikTok.
Use TIKTOK_USERNAMES on the Worker with the same list as GitHub, PRIMARY_USERNAME
matching GitHub's TIKTOK_USERNAME, and TARGET_PLATFORMS matching enabled publishers
(e.g. youtube,instagram,telegram). Do not omit an enabled destination.
After a failed run it waits 15 minutes before retrying to conserve free quotas.

A one-minute polling interval is NOT a one-minute publication guarantee.
TikTok embed freshness/blocking, Cloudflare scheduling, GitHub runner startup,
uploads and platform processing may delay results. Live discovery from
Cloudflare has NOT been verified; never activate without testing each source.

## Activation and zero-paid-usage requirement
1. Sign in to Cloudflare, verify Workers Free. Do not upgrade.
2. Verify GitHub and Apify billing, free allowances and zero paid usage controls.
   Free quotas can stop service. Zero spend plus uninterrupted service cannot
   be guaranteed without sufficient free quota. No billing controls were changed.
3. With owner approval, create a finite-expiry GitHub fine-grained token limited
   to ahmedmatwe/tiktok-agent: Actions read/write, Contents read, Metadata read.
   No publishing platform tokens are sent to the Worker.
4. Configure usernames/platforms as Worker variables. Add GITHUB_TOKEN as an
   encrypted secret: npx wrangler secret put GITHUB_TOKEN. Never commit it.
5. Deploy from scheduler/: npx wrangler deploy. No public HTTP endpoint is used.
6. Test public discovery for each source and a manual scheduled invocation.
   Confirm only one workflow_dispatch for new work and no runner for idle work.
   Baseline new sources, then upload a new test video and measure real latency.
7. Only after success, remove GitHub's schedule block, keep workflow_dispatch.
   Never disable the existing fallback before the replacement is operational.

At most three accounts means 4,320 public profile fetches daily plus GitHub
state/run API checks. Requests/CPU and API allowances must be verified on the
actual accounts. Apify is called only during a needed download, not polling.
GitHub state is the source of truth; no paid database or KV is required.

## Validation
node --test scheduler/worker.test.mjs
python -m unittest test_sources -q
Tests cover new account baselines, primary migration, source failure isolation,
partial publishing failures, credentials isolation, idle checks, active runs,
bounded retry and API errors. No live uploads were triggered by these tests.
