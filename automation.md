# 🤖 AUTOMATION.md — 100-University Free-Tier Batch Plan

Automates generation of the remaining ~99 universities using **GitHub Actions (free) + OpenRouter (free-tier models, with automatic failover across DeepSeek / Gemini / Llama / Qwen)**. Designed around a concrete goal: **finish 100 universities × 15 files in roughly 25–30 days**, unattended, at $0 (or ~$10 one-time, optional, for extra headroom).

---

## The Plan, in Numbers

| | Value |
|---|---|
| Universities remaining | ~99 (Caltech is largely done) |
| Files per university | 15 |
| Total files remaining | ~1,485 |
| Target timeline | 30 days |
| **Required pace** | **~50 files/day** |
| **Configured pace** (`MAX_FILES_PER_RUN`) | **60 files/day** (20% buffer) |
| **Projected completion** | **~25 days** of daily runs, leaving ~5 days of buffer for retries/verification |

### Why 60 files/day is comfortably achievable for free
OpenRouter's free tier alone allows **20 requests/minute**, and up to **1,000 requests/day** once a one-time (non-recurring) $10 credit is added to the account (or 50/day without it — see below). At 6 seconds between calls (well under the per-minute cap), generating 60 files takes about **6 minutes of actual API time** per day. There is enormous headroom even on the free-only tier if you skip the $10 top-up and instead rely on multi-model failover (see next section).

---

## How the Multi-Model Failover Works

Rather than depending on a single provider's daily quota, `scripts/run_batch.py` calls **OpenRouter** and, for each file, tries a prioritized list of free models:

1. `deepseek/deepseek-chat:free` — currently the strongest free-tier reasoning model for structured writing tasks like these.
2. `google/gemini-2.0-flash-exp:free` — fast, large context, generous quota.
3. `meta-llama/llama-3.3-70b-instruct:free` — reliable fallback, fast via Groq-class hardware.
4. `qwen/qwen-2.5-72b-instruct:free` — additional fallback for extra headroom.

If one model returns a 429 (rate-limited) or errors, the script **automatically moves to the next model** for that same file — no manual intervention, no lost work. Only if **all four** are exhausted does the run stop cleanly for the day (progress is checkpointed either way).

⚠️ **Free model slugs change over time** as providers rotate their free offerings. Before your first run, check the current list at [openrouter.ai/models?max_price=0](https://openrouter.ai/models?max_price=0) and update the `MODEL_FALLBACK_LIST` environment variable in the workflow file if any of the four above are no longer free.

---

## Setup Steps

### 1. Create an OpenRouter account and API key
Go to [openrouter.ai/keys](https://openrouter.ai/keys), sign up (no credit card required for the free tier), and generate a key.

**Optional but recommended:** add a one-time **$10 credit** (not a subscription) to raise your daily free-model cap from 50/day to 1,000/day. This isn't required to hit the 60 files/day target if failover across 4 models works well, but it adds significant safety margin. This is optional — the plan works without it, just with less buffer.

### 2. Add the key as a GitHub Secret
**Settings → Secrets and variables → Actions → New repository secret**
- Name: `OPENROUTER_API_KEY`
- Value: (your key)

### 3. Add these files to your repo
```
.github/workflows/generate-university-batch.yml
scripts/run_batch.py
progress/                 (auto-populated)
STATUS.md                 (already expanded to all 100 universities)
```

### 4. Commit and push
```bash
git add .github scripts progress STATUS.md
git commit -m "Add 100-university batch automation (OpenRouter multi-model)"
git push
```

### 5. Let it run
- **Automatic:** the workflow runs daily at 03:00 UTC via cron. No further action needed.
- **Manual (to speed things up or test):** Actions tab → "Generate University Files (Batch)" → Run workflow. You can trigger this as many times as you like in addition to the daily cron — e.g., running it manually 2–3 times on day one to jump-start progress.

### 6. Monitor progress
- `STATUS.md` updates automatically after every file — check the progress table any time.
- `progress/<slug>.json` holds the exact per-university checkpoint.
- Actions tab logs show which model handled each file and any failovers that occurred.

---

## Weekly Milestone Targets (for a 30-day plan starting today)

| Week | Target (cumulative) | Universities roughly complete |
|---|---|---|
| Week 1 | ~420 files | ~28 universities |
| Week 2 | ~840 files | ~56 universities |
| Week 3 | ~1,260 files | ~84 universities |
| Week 4 (+buffer) | ~1,485 files | **All 100 universities** |

If actual daily throughput falls short of 60/day (e.g., due to more frequent failovers or a provider tightening limits), the system doesn't break — it just takes proportionally longer. Check `STATUS.md` weekly against this table to see if you're on pace, and increase `MAX_FILES_PER_RUN` or trigger extra manual runs if you're behind.

---

## Quality Reality Check (read before trusting the output blindly)

Free-tier models in this pipeline **do not have live web search grounding** the way the Caltech files (built conversationally with Claude + web search in this chat) did. This means:

- Rankings, statistics, leadership names, and deadlines are more likely to be **outdated or approximate**.
- The `GENERAL_RULES` prompt instructs models to flag unverifiable claims with ⚠️, but **free models follow this instruction less reliably** than Claude does.
- **Recommended workflow:** let the batch pipeline produce a first draft for all 100 universities quickly and cheaply, then do a **manual verification pass** (ideally with Claude + web search, as was done for Caltech) on the highest-priority fields for each university — especially `overview.md` rankings/statistics and `admissions.md` deadlines — before treating the repository as authoritative.

---

## Switching to Paid Claude API Later (optional)

If, after seeing the free-tier draft quality, you want to upgrade specific universities (or all of them) to Claude-level accuracy with web search grounding, swap `call_openrouter()` in `scripts/run_batch.py` for a call to `https://api.anthropic.com/v1/messages` with the `web_search` tool enabled, using an `ANTHROPIC_API_KEY` secret. This is paid (no free tier), but selectively upgrading just the top 10–20 universities' `overview.md` and `admissions.md` files (the highest-stakes, fastest-changing content) would be a relatively small, targeted cost rather than reprocessing all 1,500 files.

---

## Official References
- [OpenRouter — API Keys](https://openrouter.ai/keys)
- [OpenRouter — Free Models](https://openrouter.ai/models?max_price=0)
- [OpenRouter — Rate Limits Documentation](https://openrouter.ai/docs/api-reference/limits)
- [GitHub Actions — Scheduled Events (cron)](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule)
- [GitHub Actions — Usage Limits](https://docs.github.com/en/actions/administering-github-actions/usage-limits-billing-and-administration)

---

*Superseded the earlier single-provider (Gemini-only) version of this plan. The multi-model failover approach exists specifically to make the "100 universities in ~1 month, for free" goal realistic.*
