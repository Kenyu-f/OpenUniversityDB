# 🤖 AUTOMATION.md — Free API Automation Setup

This automates university file generation using **GitHub Actions (free) + Gemini API (free tier)**, with automatic resume so quota limits never lose progress.

---

## ⚠️ Read this first: what "free" actually means here

| Component | Cost | Limit |
|---|---|---|
| GitHub Actions (public repo) | Free | Effectively unlimited minutes |
| Gemini API free tier | Free, no credit card | ~5–15 requests/minute, ~100–1,000 requests/day *(varies by model, and Google has cut these limits before without notice — verify current numbers at [ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits) before relying on any specific figure)* |

This is **free but not unlimited**. With the daily quota, you can realistically generate roughly **3–15 files per day** depending on the model and current limits (each of the 15 files per university = 1 API request). At that pace, one university takes **~1–5 days**, and 100 universities takes **several months** running unattended. The system below is built around that reality: it does a little work every day, checkpoints its progress, and never fails loudly when it hits a quota wall — it just picks up again tomorrow.

**If you want it faster**, the only ways are:
1. Enable Gemini billing (pay-as-you-go, cheap but not free) — rate limits jump to 150–300 RPM.
2. Use Claude API instead (higher quality, especially for citation accuracy and web-verified facts) — also paid, no free tier.
3. Run several free-tier accounts/keys in parallel (against most providers' terms for automation at scale — not recommended).

**A quality trade-off to be aware of:** the free Gemini tier generally does **not** include live web search grounding in this setup (unlike Claude with the web search tool, which is what produced the Caltech files earlier in this conversation). That means generated content is more likely to contain outdated or unverifiable claims. The `MASTER_PROMPT.md` rules instruct the model to flag anything it can't verify — but you should still **spot-check statistics, rankings, and leadership names** before treating any auto-generated file as final, exactly as we did manually for Caltech.

---

## Setup Steps

### 1. Get a free Gemini API key
Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey), sign in with a Google account, click "Create API key." No credit card needed for the free tier.

### 2. Add it as a GitHub Secret
In your repository: **Settings → Secrets and variables → Actions → New repository secret**
- Name: `GEMINI_API_KEY`
- Value: (paste your key)

### 3. Add these files to your repo
```
.github/workflows/generate-university.yml
scripts/generate_university.py
scripts/pick_next_university.py
progress/                      (empty folder is fine — auto-populated)
```

### 4. Commit and push
```bash
git add .github scripts progress
git commit -m "Add free-tier automation for university file generation"
git push
```

### 5. Trigger it

**Manual run (pick a specific university):**
Go to the **Actions** tab → "Generate University Files" → **Run workflow** → enter the university name and slug (must match a row in `STATUS.md`) → Run.

**Automatic daily runs:**
Already scheduled via cron (`0 3 * * *` = 03:00 UTC daily) in the workflow file. It will automatically:
1. Look at `STATUS.md` for a university that's 🟡 in progress (finish it first) or ⚪ not started (start the next one).
2. Generate up to `MAX_FILES_PER_RUN` (default 5) files.
3. If it hits a quota error, it stops cleanly, saves progress to `progress/<slug>.json`, and commits what it has.
4. Tomorrow's run picks up exactly where it left off.

You can change the schedule or `MAX_FILES_PER_RUN` directly in `generate-university.yml`.

### 6. Monitor progress
- `STATUS.md` is auto-updated after every file (completed count + status emoji).
- `progress/<slug>.json` holds the exact checkpoint per university (which files are done).
- Check the **Actions** tab logs any time to see what ran and why it stopped (quota vs. completed).

---

## How the resume logic works (the part you specifically asked about)

1. Every completed file is recorded immediately in `progress/<slug>.json` — not just at the end of a run.
2. If a Gemini API call returns HTTP 429 (quota/rate limit exceeded), the script:
   - Does **not** crash or fail the workflow.
   - Saves whatever was completed so far.
   - Exits cleanly.
3. On the next run (next day, or a manual re-run), the script reads `progress/<slug>.json`, skips every file already marked `completed`, and continues with the next pending file — **no wasted API calls, no lost work, no duplicate generation.**

---

## Switching to Claude API later (optional, paid)

If you later want higher-quality, web-verified output (closer to how Caltech's `overview.md`/`admissions.md` were built in this conversation), you'd swap the `call_gemini()` function in `scripts/generate_university.py` for a call to `https://api.anthropic.com/v1/messages` with a `GEMINI_API_KEY`-equivalent `ANTHROPIC_API_KEY` secret, and optionally enable the `web_search` tool for grounding. This is a paid API — there is no free tier — but token costs for a few thousand words of Markdown per file are typically small per file; costs scale with how many universities/files you generate.

---

## Official References
- [Gemini API — Rate Limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Gemini API — Pricing (free vs paid tiers)](https://ai.google.dev/gemini-api/docs/pricing)
- [GitHub Actions — Usage Limits](https://docs.github.com/en/actions/administering-github-actions/usage-limits-billing-and-administration)
- [GitHub Actions — Scheduled Events (cron)](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule)
