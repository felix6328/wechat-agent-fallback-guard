"""LLM 语义质检：只判断「这条工具返回对用户的这个请求来说是否可信」，不决定动作。

动作由 policy.py 的确定性矩阵决定（尤其支付，LLM 永远不能触发重试/扣款）。
- 接口：硅基流动官方 OpenAI 兼容 https://api.siliconflow.cn/v1/chat/completions
- temperature=0，要求 JSON；解析失败或 API 失败 → 返回 None，由调用方回退到规则判断
- 磁盘缓存：同模型同 prompt 不重复计费；用量写 data/cost/llm.jsonl（不含密钥）
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from .envload import load_siliconflow_api_key
from .paths import DATA
from . import world as W

BASE_URL = "https://api.siliconflow.cn/v1/chat/completions"

# 元 / 百万 token。来源 https://www.siliconflow.cn/pricing ，查阅 2026-11-15（Asia/Shanghai）
PRICES = {
    "Qwen/Qwen2.5-7B-Instruct": {"in": 0.0, "out": 0.0, "note": "价格页标注 (Free)"},
    "deepseek-ai/DeepSeek-V3.2": {"in": 4.0, "out": 6.0, "cache": 0.4, "note": "价格页标价"},
    "deepseek-ai/DeepSeek-V4-Flash": {"in": 3.0, "out": 9.0, "cache": 0.3,
                                      "note": "分时计价：0–2 点 / 8–24 点 ¥3 / ¥9；2–8 点 ¥1.5 / ¥4.5。本项目调用都在白天，按白天价估算"},
    "zai-org/GLM-4.5-Air": {"in": 1.0, "out": 6.0, "note": "价格页标价；只用于生成独立测试集，不做质检"},
}
SPEND_CAP_CNY = float(os.environ.get("FB_SPEND_CAP_CNY", "8.0"))   # 项目累计（含历史日志）上限


class SpendCapExceeded(RuntimeError):
    pass


def logged_spend_cny() -> float:
    """按 data/cost/llm.jsonl 累计估算的历史花费。"""
    path = DATA / "cost" / "llm.jsonl"
    if not path.exists():
        return 0.0
    tot = 0.0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        tot += cost_cny(r["model"], r.get("prompt_tokens", 0), r.get("completion_tokens", 0))
    return tot


_SPEND = {"value": None}
_SPEND_LOCK = threading.Lock()


def _charge(cny: float):
    with _SPEND_LOCK:
        if _SPEND["value"] is None:
            _SPEND["value"] = logged_spend_cny()
        _SPEND["value"] += cny
        if _SPEND["value"] > SPEND_CAP_CNY:
            raise SpendCapExceeded(f"累计估算花费 ¥{_SPEND['value']:.2f} 超过上限 ¥{SPEND_CAP_CNY}")

TYPES = ["none", "semantic_wrong", "context_mismatch", "stale", "partial", "schema_error", "amount_mismatch"]

SYSTEM = """你是微信 AI 助手调用小程序原子接口后的「返回质量质检员」。
你会看到：用户原话、Agent 解析出的请求参数、被调用的接口名、接口返回的 JSON，以及规则层给出的可疑提示（可能为空）。
你的任务：判断这条返回能不能放心地展示给用户/用于下一步，重点找规则写不出来的语义问题，例如：
- 字段之间互相矛盾（天气「晴」却有大量降水；配送距离很远却只要几分钟）
- 数值在通用范围内，但对这个城市/季节/品类明显不合常理（11 月上海零下十几度、南方城市下大雪、一碗面 80 元）
- 返回内容和用户要的对不上（问 A 店，菜单却是另一家的菜）
- 数据过期、缺失、只返回了一部分
同时要避免误报：极寒地区的低温、机场长途车费高、雨天配送慢、团购大单金额高、赠品 0 元，这些都可能是真实情况。
当前时间：{now}（Asia/Shanghai）。
只输出一个 JSON 对象，不要输出其它文字：
{{"anomalous": true/false, "type": "none|semantic_wrong|context_mismatch|stale|partial|schema_error|amount_mismatch", "confidence": 0到1之间的小数, "evidence": "引用具体字段和数值，30字以内"}}"""

# v2：针对 v1 在主测试集上的两类误报改写（样本内调参，见 eval/badcases.md），并在留出集上复核
SYSTEM_V2 = SYSTEM.replace(
    "同时要避免误报：",
    "注意：用户原话里的条件或假设（如「要是下雨就叫车」）只是用户的计划，不是对接口返回的要求，返回结果与用户的假设不一致（比如没下雨）是正常的。"
    "菜单里出现用户没点的其它菜是正常的，只有菜品整体与该商户明显不符才算 context_mismatch。"
    "分页字段（has_more / total_items）显示只返回了一小部分时，应判为 partial。\n同时要避免误报：")

USER_TMPL = """用户原话：{instruction}
请求参数：{args}
接口：{op}
接口返回：{data}
规则层可疑提示：{soft}"""


@dataclass
class LLMVerdict:
    anomalous: bool
    type: str
    confidence: float
    evidence: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cached: bool
    cost_cny: float = 0.0
    model: str = ""
    escalated: bool = False


class LLMJudge:
    def __init__(self, model: str, use_cache: bool = True, timeout: float = 60.0, prompt_version: str = "v1"):
        self.model = model
        self.prompt_version = prompt_version
        self.system = SYSTEM if prompt_version == "v1" else SYSTEM_V2
        self.key = load_siliconflow_api_key()
        self.use_cache = use_cache
        self.timeout = timeout
        self.cache_dir = DATA / "cache" / "llm"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = DATA / "cost" / "llm.jsonl"
        self._lock = threading.Lock()
        self.stats = {"calls": 0, "billed_calls": 0, "cache_hits": 0, "api_fail": 0, "parse_fail": 0,
                      "prompt_tokens": 0, "completion_tokens": 0}

    @property
    def available(self) -> bool:
        return bool(self.key)

    def _post(self, messages) -> dict:
        body = json.dumps({"model": self.model, "messages": messages, "temperature": 0, "max_tokens": 200,
                           "enable_thinking": False, "response_format": {"type": "json_object"}}).encode()
        req = urllib.request.Request(BASE_URL, data=body, method="POST", headers={
            "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read())

    def judge(self, instruction: str, op: str, args: dict, data: dict, soft_flags: list[str]) -> Optional[LLMVerdict]:
        if not self.available:
            return None
        messages = [
            {"role": "system", "content": self.system.format(now=W.ts(W.NOW))},
            {"role": "user", "content": USER_TMPL.format(
                instruction=instruction, args=json.dumps(args, ensure_ascii=False), op=op,
                data=json.dumps(data, ensure_ascii=False), soft="；".join(soft_flags) or "无")},
        ]
        h = hashlib.sha256(json.dumps([self.model, messages], ensure_ascii=False).encode()).hexdigest()
        cpath = self.cache_dir / f"{h}.json"
        cached = False
        t0 = time.perf_counter()
        resp = None
        if self.use_cache and cpath.exists():
            rec = json.loads(cpath.read_text(encoding="utf-8"))
            resp, lat, cached = rec["resp"], rec["latency_ms"], True
        else:
            _charge(0.0)  # 发请求前检查累计花费
            for attempt in range(3):
                try:
                    resp = self._post(messages)
                    break
                except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
                    time.sleep(1.5 * (attempt + 1))
            lat = (time.perf_counter() - t0) * 1000
            if resp is None:
                with self._lock:
                    self.stats["calls"] += 1
                    self.stats["api_fail"] += 1
                return None
            cpath.write_text(json.dumps({"resp": resp, "latency_ms": lat}, ensure_ascii=False), encoding="utf-8")
        usage = resp.get("usage", {}) or {}
        pt, ct = int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))
        with self._lock:
            self.stats["calls"] += 1
            self.stats["prompt_tokens"] += pt
            self.stats["completion_tokens"] += ct
            if cached:
                self.stats["cache_hits"] += 1
            else:
                self.stats["billed_calls"] += 1
                _charge(cost_cny(self.model, pt, ct))
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "model": self.model,
                                        "prompt_version": self.prompt_version, "prompt_tokens": pt, "completion_tokens": ct, "latency_ms": round(lat, 1),
                                        "req_hash": h[:16]}) + "\n")
        try:
            text = resp["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", text, re.S)
            obj = json.loads(m.group(0))
            typ = str(obj.get("type", "none"))
            if typ not in TYPES:
                typ = "semantic_wrong"
            anomalous = bool(obj.get("anomalous"))
            conf = float(obj.get("confidence", 0.5))
            return LLMVerdict(anomalous, typ if anomalous else "none", conf, str(obj.get("evidence", ""))[:80],
                              pt, ct, lat, cached, cost_cny(self.model, pt, ct), self.model)
        except Exception:
            with self._lock:
                self.stats["parse_fail"] += 1
            return None


def cost_cny(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p = PRICES.get(model, {"in": 0, "out": 0})
    return prompt_tokens / 1e6 * p["in"] + completion_tokens / 1e6 * p["out"]


class CascadeJudge:
    """级联：先用快 / 便宜的小判官；小判官判异常、或置信度低于 tau 时，升级给大判官终审。
    返回的时延 = 小 + 大（串行），费用 = 两者之和。"""

    def __init__(self, small: "LLMJudge", big: "LLMJudge", tau: float = 0.0):
        self.small, self.big, self.tau = small, big, tau
        self.model = f"cascade({small.model}→{big.model}, tau={tau})"
        self.stats = {"calls": 0, "escalated": 0}
        self._lock = threading.Lock()

    @property
    def available(self):
        return self.small.available and self.big.available

    def judge(self, instruction, op, args, data, soft_flags):
        v1 = self.small.judge(instruction, op, args, data, soft_flags)
        with self._lock:
            self.stats["calls"] += 1
        if v1 is not None and not v1.anomalous and v1.confidence >= self.tau:
            return v1
        v2 = self.big.judge(instruction, op, args, data, soft_flags)
        with self._lock:
            self.stats["escalated"] += 1
        if v2 is None:
            return v1
        if v1 is None:
            v2.escalated = True
            return v2
        return LLMVerdict(v2.anomalous, v2.type, v2.confidence, v2.evidence,
                          v1.prompt_tokens + v2.prompt_tokens, v1.completion_tokens + v2.completion_tokens,
                          v1.latency_ms + v2.latency_ms, v1.cached and v2.cached,
                          v1.cost_cny + v2.cost_cny, self.model, True)


class VerdictCache:
    """产品侧的「判定缓存」：同一接口、同样参数、同样返回（时间戳按小时取整）在 TTL 内复用判定，
    命中时时延和费用为 0。与评测用的磁盘缓存（只为不重复付费，回放首次时延）是两回事。"""

    VOLATILE = ("updated_at", "menu_updated_at")

    def __init__(self):
        self.store = {}
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()

    def key(self, op, args, data, soft_flags):
        d = dict(data or {})
        for k in self.VOLATILE:
            if isinstance(d.get(k), str):
                d[k] = d[k][:13]   # 取到小时
        return hashlib.sha256(json.dumps([op, args, d, sorted(soft_flags)], ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    def get(self, k):
        with self._lock:
            v = self.store.get(k)
            if v is None:
                self.misses += 1
            else:
                self.hits += 1
            return v

    def put(self, k, v):
        with self._lock:
            self.store[k] = v
