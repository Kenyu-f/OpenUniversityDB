#!/usr/bin/env python3
"""
run_batch.py

Daily batch orchestrator for the 100-university plan.

- Calls OpenRouter (https://openrouter.ai), trying a list of FREE models in order.
  If one model is rate-limited (429) or errors out, it automatically fails over
  to the next model in the list -- this is what lets Gemini + DeepSeek + Llama
  free tiers combine into more total daily throughput than any single provider.
- Works across MULTIPLE universities in a single run: it keeps generating files,
  university after university, until MAX_FILES_PER_RUN is reached for the day.
- Fully resumable: every completed file is checkpointed immediately in
  progress/<slug>.json. If the run stops (quota exhausted on ALL fallback
  models, or MAX_FILES_PER_RUN reached), it exits cleanly and picks up exactly
  where it left off on the next scheduled run.

Usage (no arguments needed -- it reads STATUS.md automatically):
    python scripts/run_batch.py

Environment variables:
    OPENROUTER_API_KEY   - required. Get one free at https://openrouter.ai/keys
    MAX_FILES_PER_RUN    - default 60 (tuned for the "100 universities in ~30 days" plan)
    SECONDS_BETWEEN_CALLS - default 6 (stays well under free-tier RPM limits)
    MODEL_FALLBACK_LIST  - comma-separated OpenRouter model IDs, in priority order.
                            Default list below. Verify current free model IDs at
                            https://openrouter.ai/models?max_price=0 -- free model
                            slugs change over time as providers rotate offerings.
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROGRESS_DIR = os.path.join(REPO_ROOT, "progress")
UNIVERSITIES_DIR = os.path.join(REPO_ROOT, "universities")
STATUS_FILE = os.path.join(REPO_ROOT, "STATUS.md")

API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not API_KEY:
    print("ERROR: OPENROUTER_API_KEY is not set.")
    sys.exit(1)

MAX_FILES_PER_RUN = int(os.environ.get("MAX_FILES_PER_RUN", "60"))
SECONDS_BETWEEN_CALLS = int(os.environ.get("SECONDS_BETWEEN_CALLS", "6"))

# Default free-model fallback chain. VERIFY current free slugs periodically at
# https://openrouter.ai/models?max_price=0 -- providers add/remove/rename
# free-tier models fairly often.
DEFAULT_MODELS = [
    "deepseek/deepseek-chat:free",
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
]
MODEL_FALLBACK_LIST = os.environ.get(
    "MODEL_FALLBACK_LIST", ",".join(DEFAULT_MODELS)
).split(",")

FILE_SPECS = [
    ("overview.md", "history, campus, organization, schools/divisions, research strengths, "
                     "global rankings, notable achievements, statistics, student population "
                     "(grad/undergrad), research expenditures, collaborations"),
    ("admissions.md", "undergraduate admissions, graduate admissions, international applicants, "
                       "required exams, GPA expectations, English requirements, recommendation "
                       "letters, statement of purpose, interviews, deadlines, application portals, "
                       "funding for admitted students"),
    ("undergraduate_research.md", "every undergraduate research opportunity: summer programs, "
                                   "fellowships, independent research, research assistant positions, "
                                   "undergraduate publications, research awards, application process"),
    ("graduate_research.md", "PhD programs, Master's programs, advisor selection, laboratory "
                              "matching, qualifying exams, dissertation process, teaching "
                              "assistantships, research assistantships"),
    ("laboratories.md", "a Markdown table of EVERY laboratory with columns: Laboratory | "
                         "Department | Research Areas | Director | Official Website. Do not "
                         "intentionally omit laboratories."),
    ("professors.md", "a Markdown table of CURRENT faculty with columns: Name | Department | "
                       "Research Areas | Personal Website | Google Scholar | Lab"),
    ("research_centers.md", "every research institute/center: mission, research topics, "
                             "participating departments, director, official website"),
    ("internships.md", "internal internships, external internships, industrial partnerships, "
                        "national-lab-equivalent programs, visiting student opportunities, summer "
                        "internships, undergraduate and graduate internships"),
    ("funding.md", "scholarships, fellowships, grants, assistantships, tuition support, external "
                    "funding opportunities"),
    ("publications.md", "publication repositories, institutional repository, thesis archive, open "
                         "access policy, library resources"),
    ("companies.md", "startups, spin-off companies, technology transfer, innovation ecosystem, "
                      "entrepreneurship programs, notable examples"),
    ("alumni.md", "a Markdown table of notable alumni: Name | Field | Achievement | Award "
                   "(Nobel/Turing/Fields/etc.) | Company Founded (if any)"),
    ("roadmap.md", "a roadmap for a high school student aiming to conduct research at this "
                    "university: high school prep, mathematics, core science/domain track, "
                    "programming, research experience, competitions, reading list, university "
                    "prep, graduate school prep"),
    ("resources.md", "official websites, department websites, laboratory websites, YouTube "
                      "channels, podcasts, lecture series, course materials/OCW, digital "
                      "libraries, student organizations"),
]

GENERAL_RULES = """
You are an academic research assistant building a long-term public GitHub knowledge base
about leading research universities. Follow these rules strictly:
- Write in Markdown with clear section headings.
- Prefer official university sources. Include an "Official References" section with
  Markdown links at the end.
- If you cannot verify something against an official source, say so explicitly with
  "⚠️ Could not verify against an official source" rather than guessing.
- Do not speculate or invent statistics, names, or URLs.
- Keep tone objective and encyclopedic. No marketing language.
- Use tables wherever structured/tabular data is requested.
- Be exhaustive within the file.
"""


class AllModelsExhausted(Exception):
    pass


def call_openrouter(prompt: str) -> str:
    """Try each model in MODEL_FALLBACK_LIST in order. Returns generated text
    from the first one that succeeds. Raises AllModelsExhausted if every
    model in the list is rate-limited or erroring."""
    last_error = None
    for model in MODEL_FALLBACK_LIST:
        model = model.strip()
        if not model:
            continue
        url = "https://openrouter.ai/api/v1/chat/completions"
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", "ignore")
            if e.code == 429:
                print(f"  [{model}] rate-limited (429) -- failing over to next model")
                last_error = f"429 on {model}"
                continue
            print(f"  [{model}] error {e.code}: {body_text[:200]} -- failing over")
            last_error = f"{e.code} on {model}"
            continue
        except Exception as e:
            print(f"  [{model}] exception: {e} -- failing over")
            last_error = str(e)
            continue

    raise AllModelsExhausted(f"All models in fallback list exhausted. Last error: {last_error}")


def load_progress(slug: str) -> dict:
    path = os.path.join(PROGRESS_DIR, f"{slug}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"completed": [], "pending": [name for name, _ in FILE_SPECS]}


def save_progress(slug: str, progress: dict):
    os.makedirs(PROGRESS_DIR, exist_ok=True)
    path = os.path.join(PROGRESS_DIR, f"{slug}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


ROW_RE = re.compile(
    r"\|\s*\d+\s*\|\s*(?P<name>[^|]+?)\s*\|\s*[^|]+\|\s*[^|]+\|\s*`(?P<slug>[^`]+)`\s*\|"
    r"\s*(?P<done>\d+)/15\s*\|\s*(?P<status>[🟢🟡⚪🔺])\s*\|"
)


def load_status_rows():
    if not os.path.exists(STATUS_FILE):
        return []
    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    return [m.groupdict() for m in ROW_RE.finditer(content)]


def update_status_md(name: str, slug: str, completed_count: int, total: int = 15):
    if not os.path.exists(STATUS_FILE):
        return
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        status_icon = "🟢" if completed_count == total else ("🟡" if completed_count > 0 else "⚪")
        pattern = re.compile(rf"(\|[^\n]*`{re.escape(slug)}`[^\n]*\|)\s*\d+/15\s*\|\s*[🟢🟡⚪🔺][^\n]*\|")

        def _replace(m):
            return f"{m.group(1)} {completed_count}/15 | {status_icon} |"

        new_content, n = pattern.subn(_replace, content)
        if n > 0:
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                f.write(new_content)
    except Exception as e:
        print(f"WARNING: STATUS.md auto-update failed non-fatally: {e}")


def generate_one_file(name: str, slug: str, filename: str, requirements: str) -> str:
    prompt = f"""{GENERAL_RULES}

Generate the file `{filename}` for the university "{name}".
This file must include: {requirements}

Output ONLY the Markdown content of the file itself (start with a top-level `# {name} — <Section Title>` heading). Do not include any commentary before or after the file content.
"""
    return call_openrouter(prompt)


def run():
    rows = load_status_rows()
    if not rows:
        print("No rows found in STATUS.md. Nothing to do.")
        return

    # Priority: universities already 🟡 in progress first, then ⚪ not started,
    # in the order they appear in STATUS.md (i.e. rank order).
    ordered = [r for r in rows if r["status"] == "🟡"] + [r for r in rows if r["status"] == "⚪"]

    files_done_this_run = 0

    for row in ordered:
        if files_done_this_run >= MAX_FILES_PER_RUN:
            break

        name, slug = row["name"].strip(), row["slug"].strip()
        out_dir = os.path.join(UNIVERSITIES_DIR, slug)
        os.makedirs(out_dir, exist_ok=True)
        progress = load_progress(slug)

        for filename, requirements in FILE_SPECS:
            if filename in progress["completed"]:
                continue
            if files_done_this_run >= MAX_FILES_PER_RUN:
                break

            print(f"[{slug}] Generating {filename} ...")
            try:
                text = generate_one_file(name, slug, filename, requirements)
            except AllModelsExhausted as e:
                print(f"All free models exhausted for today: {e}")
                print("Stopping cleanly. Progress is saved. Next scheduled run will resume.")
                save_progress(slug, progress)
                update_status_md(name, slug, len(progress["completed"]))
                print(f"Generated {files_done_this_run} file(s) this run before stopping.")
                return

            out_path = os.path.join(out_dir, filename)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text.strip() + "\n")

            progress["completed"].append(filename)
            if filename in progress["pending"]:
                progress["pending"].remove(filename)
            save_progress(slug, progress)
            update_status_md(name, slug, len(progress["completed"]))

            files_done_this_run += 1
            time.sleep(SECONDS_BETWEEN_CALLS)

    print(f"Run complete. Generated {files_done_this_run} file(s) this run.")


if __name__ == "__main__":
    run()
