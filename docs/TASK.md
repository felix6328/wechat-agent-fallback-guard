# Task 02 — Fallback Agent v2: put the quality gateway in front of REAL sandbox APIs

> Repo: existing `https://github.com/felix6328/wechat-agent-fallback-guard` (local name `wxg-fallback-agent`). Effort: ≈ 3.5 days (+ optional 2–3 days mini-program track).
> Code/comments English; README/DESIGN/面试讲法 Chinese.

## 0. Background
v1 is a pure-stdlib prototype of a *tool-response quality gateway* for an AI assistant that calls mini-program atomic APIs (context: WeChat's AI assistant 「小微」 and 小程序 AI 开发模式, cited in DESIGN.md from public news/docs). All 5 services (`ride/food/weather/pay/map`) are **simulated** in `fbagent/mock_apis.py` with seeded fault injection. Interviewers' natural question: *"Did you ever run this against a real API?"* the author cannot get WeChat Pay (individuals cannot get a merchant ID; APIv3 has no sandbox; the V2 仿真测试系统 also needs a merchant ID). So v2 uses **real, individually accessible substitutes**:
- **Payment → Alipay Open Platform sandbox (支付宝开放平台沙箱)**, open to personal accounts.
- **Weather / geocode / POI → Amap Web Service API (高德开放平台)**, personal key.
- A local **fault-injection proxy** sits between the agent and these real APIs, mutating real responses to create the "200 OK but wrong data" faults.

### Scenario (README first screen, Chinese)
**一句话：** 用户在聊天里说「帮我查下明天广州会不会下雨，顺便把这单 38 元的外卖付了」，Agent 调真实的天气接口和真实的支付沙箱。接口返回「成功但数据错了」（城市串了、单位错了、天气过期了），或者支付扣款后超时，这时网关要在用户看到之前拦住：先查单，不重复扣款，并告诉用户数据可能不对。
Persona「小林」：通勤路上单手发语音，不会核对返回数据；只要 AI 说错一次天气，或者多扣一次钱，她就不再用了。

## 1. Get the repo
```bash
git clone https://github.com/felix6328/wechat-agent-fallback-guard.git && cd wechat-agent-fallback-guard
git checkout -b v2-real-sandbox
```
Key files: `fbagent/mock_apis.py` (ToolResult, faults, FAULTABLE ops, TIMEOUT_MS), `fbagent/rules.py` (`check()` → RuleVerdict with hard/soft flags), `fbagent/agent.py` (Agent, `_pay`, `_weather`, policy), `fbagent/llm_judge.py`, `fbagent/evaluate.py`, `eval/run_eval.py`, `configs/policy.json`, `configs/faults.json`, `fbagent/envload.py` (loads only `SILICONFLOW_API_KEY` from `.env.local` or `FB_ENV_FILE`), spend cap `FB_SPEND_CAP_CNY`. Tests: `python -m pytest -q` or `python -m unittest` (check which v1 uses). **Do not break v1 results**: the mock backend stays the default; the real backend is opt-in (`--backend real`).

## 2. Stack
v1 is stdlib-only; keep the core stdlib. The new adapters can add `requirements-real.txt`: `alipay-sdk-python` (official SDK, PyPI name `alipay-sdk-python`; verify current name/version on https://github.com/alipay/alipay-sdk-python-all), `cryptography` if needed for RSA2, `httpx` optional (or urllib).

## 3. Data / API sources
### 3.1 Alipay sandbox
- Docs: https://opendocs.alipay.com/common/097lz0 (沙箱环境; the page is a JS app, open it in a browser), API list https://opendocs.alipay.com/open/
- Gateway: `https://openapi-sandbox.dl.alipaydev.com/gateway.do` (older `https://openapi.alipaydev.com/gateway.do` — verify which one the console shows). Signing RSA2, charset utf-8, JSON `biz_content`.
- APIs to use: `alipay.trade.precreate` (QR, no buyer needed), `alipay.trade.page.pay` (web cashier, sandbox buyer logs in), `alipay.trade.query`, `alipay.trade.refund`, `alipay.trade.close`, `alipay.trade.fastpay.refund.query`; async notify optional (needs a public URL → skip, poll with query instead and document why).
- Known sandbox limits (document them): maintenance roughly **Sunday 12:00 – Monday 12:00** (Beijing time), sandbox app Android only, **one refund per order**, sandbox balances are fake. Integration tests must auto-skip with a clear message when the gateway is down.
- Idempotency: `out_trade_no` = deterministic hash of (session_id, order_id) — reuse on retry; never create a second order after a timeout; always `query` first.

### 3.2 Amap Web Service API
- Docs: https://lbs.amap.com/api/webservice/summary ; key from console https://console.amap.com/dev/key/app (service platform = Web服务).
- Endpoints: `https://restapi.amap.com/v3/weather/weatherInfo?city=<adcode>&extensions=base|all&key=…`, `https://restapi.amap.com/v3/geocode/geo?address=…&key=…`, `https://restapi.amap.com/v3/place/text?keywords=…&city=…&key=…`. Without a key the API returns `INVALID_USER_KEY` (verified).
- Quotas for personal verified developers are small (weather/geocode ≈ 5,000/day, search ≈ 100/day; verify in console). Cache every response to `cache/amap/` (gitignored) and design the eval to fit < 500 calls total.

### 3.3 Food / ride
No real API is available to an individual; keep them simulated and say so. Only `weather`, `map` (geocode/POI) and `pay` become real.

## 4. Work items
1. **Backend abstraction (0.5 d):** `fbagent/backends/{base.py,mock.py,real.py}` returning the same `ToolResult`. `Env` picks backend via config/CLI.
2. **Amap adapter (0.5 d):** `weather.query` → Amap weatherInfo (map city name → adcode via geocode, cached), normalise to v1 schema (`temp_high/low`, `condition`, `updated_at`, `city`). `map.route`/POI optional.
3. **Alipay adapter (1 d):** `pay.create` → precreate (or page.pay for the manual demo), `pay.query` → trade.query, plus refund/close utilities. RSA2 keys loaded from env (PEM string or file path).
4. **Fault-injection proxy (0.5 d):** wraps the real backend; applies v1 fault kinds to real responses: `sem_city` (swap city), `sem_range_temp`, unit faults (fen↔yuan on amount echo), `stale_*` (rewrite `reporttime`), `schema_missing`, `timeout_after_charge` (call precreate/pay, then drop the response), `http_429/500`. Ground truth recorded exactly like v1 (`Env.gt`).
5. **Eval on real backend (0.5 d):** new set `data/testset_real.json` of 40 instructions (weather in 15+ real cities, pay flows) × 3 seeds; variants: no-check / rules / rules+LLM. Report: user-harm rate, false-alarm rate on unmodified real responses (**this is the new, valuable number**: how often rules/LLM flag genuinely correct real data), duplicate-charge count (must be 0), real latency P50/P95 including network. `eval/results_real.md`.
6. **Docs (0.5 d):** README section 「v2：真实沙箱接口」, DEMO step with sandbox, 面试讲法 update.

### Optional track — personal mini-program in AI 开发模式 (2–3 d, only if the author confirms eligibility)
Docs: https://developers.weixin.qq.com/miniprogram/dev/ai/guide.html . Official docs list no subject restriction; a second-hand source says personal mini-programs can apply for tool-type skills only. **Not confirmed.** If the author confirms, build one tool-type SKILL (e.g. "城市天气核对") whose atomic API returns `isError/content/structuredContent` from the gateway. No payment, no 深度合成 categories. Otherwise skip entirely.

## 5. Environment variables (names only; `.env.example` in this folder)
`SILICONFLOW_API_KEY`, `AMAP_KEY`, `ALIPAY_APP_ID`, `ALIPAY_APP_PRIVATE_KEY` (or `ALIPAY_APP_PRIVATE_KEY_FILE`), `ALIPAY_PUBLIC_KEY` (Alipay's public key, not the app's), `ALIPAY_GATEWAY`, `FB_SPEND_CAP_CNY`, `FB_ENV_FILE`. Extend `envload.py` with an explicit allow-list; it must still never read other variables. Private key files: outside the repo or in a gitignored `secrets/` with chmod 600.

## 6. Acceptance criteria
1. `python -m pytest -q` (or the v1 runner) passes offline; v1 eval numbers reproduce unchanged with the mock backend (re-run `eval/run_eval.py` on one config and diff).
2. `python scripts/demo.py --backend real --case weather_gz` prints real Amap weather for 广州 with source + `reporttime`; with `--inject sem_city` the gateway flags and degrades with a disclosure.
3. Pay flow in sandbox: `scripts/pay_sandbox_demo.py` creates a precreate order (prints QR URL), simulates `timeout_after_charge`, the agent calls `trade.query` before any retry, and **the sandbox shows exactly one trade** for that `out_trade_no`. Close/refund path tested once. Log trade numbers in `eval/sandbox_log.md` (no keys, no buyer account details).
4. `eval/results_real.md` exists with: harm rate per variant, false-alarm rate on clean real responses, duplicate charges = 0, latency, cost, API call counts vs quota.
5. All public claims checked: `rg -n "微信支付|WeChat Pay|小微"` — any mention must be background/analogy only; no sentence claims integration with WeChat Pay or 小微. Fix `fbagent/agent.py` user-facing text "结果会通过微信支付通知你" → neutral "支付结果会通过支付平台通知你".
6. Integration tests skip cleanly (not fail) without keys or during sandbox maintenance.
7. Secret scan clean; `.gitignore` covers `secrets/`, `cache/`, `.env.local`.

## 7. Deliverables
README v2 section (scenario first, then "为什么用支付宝沙箱和高德：个人拿不到微信支付商户号，详见可行性说明"), `DEMO.md` (sandbox demo, including the manual sandbox-buyer step), `面试讲法.md` additions (why substitute, what transfers to WeChat: idempotency, query-first, rule/LLM split; what doesn't: real merchant risk control), `eval/results_real.md`, updated `COST.md`.

## 8. DO NOT
- Do not use Stripe (mainland China unsupported; test mode would require a false country declaration).
- Do not claim WeChat Pay / 小微 / merchant integration; do not register any account for the author.
- Do not call Alipay production gateway; sandbox only. Do not store buyer passwords.
- Do not exceed Amap quotas; cache.
- Do not let the LLM decide anything on payments (v1 principle).
- Do not print keys; do not push without the author's say-so.
