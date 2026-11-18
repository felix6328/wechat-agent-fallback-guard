# AGENTS.md — rules for coding agents in this repository

This repo is a personal portfolio project by the author (AI PM internship applicant). It is **not** a production system of Tencent, ByteDance, Riot, Wildfire Games or any other company. Read `docs/TASK.md` (the task brief) before writing code.

## Working style
- Work in small milestones as listed in `docs/TASK.md`. **Commit at every milestone checkpoint** (and at least every ~2 hours of work) with a descriptive message, so an interrupted session never loses work. Do not squash or rewrite pushed history.
- Before each commit: run the test suite and the secret scan (below). Never commit with failing tests unless the commit message says `WIP:` and why.
- Prefer boring, readable Python 3.11+ (type hints, small functions, docstrings on public functions). Use the stdlib where reasonable; pin third-party deps in `requirements.txt`.
- Put all thresholds, model ids, prices and paths in `configs/*.yaml`, not in code.
- Every number that appears in README/DEMO/面试讲法 must be produced by a script in this repo and written to `eval/*.md` or `eval/*.json`. Never type numbers by hand.
- Network calls: add a disk cache keyed by request hash (cache dir is gitignored), retries with backoff, and a spend cap (`*_SPEND_CAP_CNY`) for paid APIs. Be polite to public servers (≤ 2 requests/second unless the provider documents more).

## How to run
- Create a venv: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Tests: `python -m pytest -q` (unit tests must not call paid APIs or the network; mark integration tests with `@pytest.mark.network` and skip them by default).
- Each repo's README has a "Quick start" that must work from a fresh clone.

## Secrets (hard rules)
- Use the user-selected shared file via FB_ENV_FILE or a gitignored .env.local (chmod 600). Commit only `.env.example` with **variable names and empty or placeholder values**.
- Load only the specific variables you need; never print, log, or echo secret values; never put them in test fixtures, notebooks, screenshots or error messages.
- Before every commit run: `git diff --cached | grep -nE 'sk-[A-Za-z0-9]{16,}|BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|(KEY|SECRET|TOKEN)=[^ <]{12,}' && echo "STOP: possible secret"`. If anything matches, do not commit.
- `.gitignore` must include: `.env`, `.env.local`, `.venv/`, `__pycache__/`, cache dirs, raw downloaded third-party assets.

## Honesty rules
- Label simulated, synthetic, provisional (AI-labelled) or sampled data explicitly in README and in output reports.
- Do not claim integration with WeChat Pay, 小微, Stripe, Douyin/Doubao in-app traffic, or any company-internal system.
- Do not scrape websites at scale or bypass rate limits/ToS. Use official APIs or small, documented, de-identified samples.
- Respect licences: keep third-party licence files, add attribution where required (e.g. CC-BY-SA art).

## Deliverables every repo must have
- `README.md` that **opens with the user scenario** (one sentence: who, what moment, what pain, what the tool does, the result) and a scenario diagram, then results, then architecture.
- `DEMO.md`: a 3–5 minute demo script with exact commands.
- `面试讲法.md`: a 30-second pitch and likely interview follow-ups with honest answers (in Chinese).
- `eval/` with reproducible results and a badcase list.

## Project-specific (wechat-agent-fallback-guard v2)
- Task brief: `docs/TASK.md` (= `02_fallback_agent_v2.md`). Work on branch `v2-real-sandbox`.
- Core stays stdlib; real adapters' deps go in `requirements-real.txt`.
- Mock backend remains default; v1 results must reproduce unchanged.
- Payments: idempotent `out_trade_no`, query-before-retry, LLM never involved. Alipay **sandbox** only.
- `fbagent/envload.py` uses an explicit allow-list (SILICONFLOW_API_KEY, AMAP_KEY, ALIPAY_*); never read other vars; private key files outside the repo or in gitignored `secrets/`.
- Integration tests (`@network`) must skip cleanly without keys or during sandbox maintenance.
