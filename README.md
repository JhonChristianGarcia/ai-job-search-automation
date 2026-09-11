# job-search-automation

Personal automation for applying to jobs on Jobstreet, Indeed, and LinkedIn. It drives a real
browser session, scrapes job listings, uses an LLM agent to decide whether a job is worth
applying to based on my resume and preferences, and (where supported) fills out the application
form automatically.

This is a personal tool tailored to my own job search, resume, and preferences. It's shared here
mostly for reference — you'd need to swap in your own resume, context, and credentials to make it
useful for yourself.

## How it works

Each site (`Jobstreet/`, `Indeed/`, `LinkedIn/`) has its own scraper/automation module that:

1. Launches a browser and logs into the site using a persistent browser profile (so you don't
   have to log in every run).
2. Searches for jobs based on a list of keywords.
3. Extracts the job title/description and passes it to the job analyzer agent
   (`custom_agents/job_analyzer.py`), which compares it against my resume and preferences and
   returns a match decision.
4. If it's a match, tries to fill out and submit the application form using the form
   evaluator/extractor agents in `custom_agents/`.

`base_page.py` holds the shared browser bootstrap logic (persistent context, stealth plugin,
skip-keyword filtering) that each site module builds on.

### Browser profile / persistent login

Instead of automating a fresh, unauthenticated browser session every time, this project reuses a
real Brave browser profile so it's already logged into Jobstreet/Indeed/LinkedIn and won't get
flagged as a bot as easily.

`base_page.py` launches Playwright against a copy of your Brave user data directory
(`C:\Users\<you>\AppData\Local\BraveSoftware\Brave-Browser\PlaywrightProfile`), rather than the
live Brave profile directory, so Brave itself can stay open while automation runs.

`reset_browser_data.sh` is a helper to (re)create that `PlaywrightProfile` folder by copying your
real Brave `User Data` into it. Run it whenever you want the automation profile to pick up a fresh
login/cookie state from your actual browser. Note it currently assumes Brave is installed at the
default path and does `rm -rf` on the existing `PlaywrightProfile` before copying — check the
paths before running if your setup differs.

If you're not on Brave/Windows, you'll need to adjust the `executable_path` and `user_data_dir` in
`base_page.py` to point at your own browser.

### Context and personal preferences

`context/context.py` builds the prompt used by the job analyzer agent (resume + matching rules).
It pulls in:

- `context/resume.pdf` — resume used for matching, parsed via `pymupdf4llm`.
- `context/additional_context.py` — **not committed to git** (see `.gitignore`). This is where
  personal preferences, non-negotiables, and other info I don't want public live. If you clone
  this repo, that file won't exist and you'll need to create your own before anything that
  imports it will run.

## Project structure

```
Jobstreet/          Jobstreet scraper + apply flow
Indeed/              Indeed scraper + apply flow
LinkedIn/            LinkedIn scraper + apply flow
custom_agents/       LLM agents: job match analysis, form field extraction, form filling
context/             Resume + prompt context (partially gitignored, see above)
utils/               Shared helpers (HTML simplification, field extraction, alerts, logging)
base_page.py         Shared Playwright/browser bootstrap used by all site modules
main.py              Placeholder entry point, not used for the automation
```

## Entry points

- **`run-all-automation.sh`** — the main entry point. Runs Jobstreet, Indeed, and LinkedIn
  automation concurrently (each as a background job) and waits for all of them to finish.

  ```bash
  ./run-all-automation.sh
  ```

- **`run-jobstreet-jobsearch-automation.sh`**, **`run-indeed-jobsearch-automation.sh`**,
  **`run-linkedin-jobsearch-automation.sh`** — run a single site's automation on its own, useful
  for testing/debugging one flow without kicking off the others.

- **`reset_browser_data.sh`** — rebuilds the Playwright browser profile from your real Brave
  profile (see above). Not part of the normal run flow, only run it when you need to refresh the
  login state.

All scripts run through `uv`, e.g. the individual runners just do:

```bash
uv run python -m Indeed.indeed
```

## Setup

- Requires Python 3.12+ and [`uv`](https://github.com/astral-sh/uv).
- Copy your own resume to `context/resume.pdf`.
- Create `context/additional_context.py` with your own preferences (gitignored, no template
  provided here since the format is tied to how `context/context.py` consumes it).
- Set up a `.env` with the API keys the agents need (OpenAI/Groq/OpenRouter/HF depending on which
  model backend you're using — see `custom_agents/`).
- Run `reset_browser_data.sh` once to seed the Playwright browser profile from your local Brave
  install.

Install dependencies with:

```bash
uv sync
```
