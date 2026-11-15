"""LLM function calling 解析指令，词表解析作兜底。

- 用 OpenAI 兼容的 tools / tool_choice，让模型填一个结构化的 make_plan(...)
- 输出必须通过词表校验（城市、商户、菜名、地点都要在模拟世界里存在）；不通过或调用失败 → 回退 parser.parse()
- 磁盘缓存 + 用量日志（data/cost/llm.jsonl，purpose=parse）
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
import urllib.error
import urllib.request

from .envload import load_siliconflow_api_key
from .llm_judge import BASE_URL, _charge, cost_cny
from .parser import PLACES, parse
from .paths import DATA
from . import world as W

TOOL = {
    "type": "function",
    "function": {
        "name": "make_plan",
        "description": "把用户的一句话解析成微信 AI 助手要执行的计划",
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "enum": ["weather", "weather_ride", "food_menu", "food_order", "ride", "route", "unknown"],
                           "description": "weather 查天气；weather_ride 根据天气决定是否叫车；food_menu 看菜单/问有没有某道菜；food_order 点外卖；ride 打车报价；route 查路线"},
                "city": {"type": "string"},
                "date": {"type": "string", "enum": ["今天", "明天", "后天"]},
                "restaurant": {"type": "string"},
                "dish": {"type": "string", "description": "food_menu 时用户问到的菜，没有就省略"},
                "items": {"type": "array", "items": {"type": "object", "properties": {
                    "name": {"type": "string"}, "qty": {"type": "integer"}}, "required": ["name", "qty"]}},
                "pay": {"type": "boolean", "description": "用户是否明确要求付款"},
                "origin": {"type": "string"}, "dest": {"type": "string"},
                "mode": {"type": "string", "enum": ["drive", "walk"]},
            },
            "required": ["intent"],
        },
    },
}


def _system():
    menus = "；".join(f"{r}：" + "、".join(i["name"] for i in info["items"]) for r, info in W.RESTAURANTS.items())
    return ("你是微信 AI 助手的指令解析器，只能调用 make_plan。可用城市：" + "、".join(W.WEATHER) +
            "（「魔都」=上海，「帝都」=北京，「羊城」=广州，「冰城」=哈尔滨，「蓉城」=成都）。商户与菜单：" + menus +
            "。地点：" + "、".join(PLACES) + "（「单位」「公司」都指公司，「机场」指浦东机场，「火车站」指虹桥火车站）。"
            "菜名必须写成菜单里的原名。没说日期就是今天。没说数量就是 1。用户说的「X 的话 / 要是 X 就叫车」是 weather_ride。")


def _norm_item(rest, name):
    names = [i["name"] for i in W.RESTAURANTS[rest]["items"]]
    if name in names:
        return name
    cand = [n for n in names if name in n or n.split("（")[0] in name]
    return cand[0] if len(cand) == 1 else None


def validate(args: dict):
    it = args.get("intent")
    if it in ("weather", "weather_ride"):
        if args.get("city") not in W.WEATHER:
            return None
        plan = {"intent": it, "city": args["city"], "date": W.DATES.get(args.get("date") or "今天", W.DATES["今天"])}
        if it == "weather_ride":
            if args.get("origin") not in PLACES or args.get("dest") not in PLACES:
                return None
            plan.update(origin=args["origin"], dest=args["dest"])
        return plan
    if it in ("ride", "route"):
        if args.get("origin") not in PLACES or args.get("dest") not in PLACES:
            return None
        try:
            W.route(args["origin"], args["dest"])
        except KeyError:
            return None
        plan = {"intent": it, "origin": args["origin"], "dest": args["dest"]}
        if it == "route":
            plan["mode"] = args.get("mode") or "drive"
        return plan
    if it in ("food_menu", "food_order"):
        rest = args.get("restaurant")
        if rest not in W.RESTAURANTS:
            return None
        if it == "food_menu":
            dish = args.get("dish")
            if dish:
                n = _norm_item(rest, dish)
                dish = n.split("（")[0] if n else None
            return {"intent": "food_menu", "restaurant": rest, "dish": dish}
        items = []
        for x in args.get("items") or []:
            n = _norm_item(rest, x.get("name", ""))
            if not n:
                return None
            items.append({"name": n, "qty": int(x.get("qty") or 1)})
        if not items:
            return None
        return {"intent": "food_order", "restaurant": rest, "items": items, "pay": bool(args.get("pay"))}
    return None


class LLMParser:
    def __init__(self, model="deepseek-ai/DeepSeek-V4-Flash", use_cache=True):
        self.model, self.use_cache = model, use_cache
        self.key = load_siliconflow_api_key()
        self.cache_dir = DATA / "cache" / "parser"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.stats = {"calls": 0, "llm_ok": 0, "fallback": 0}

    def _post(self, messages):
        body = json.dumps({"model": self.model, "messages": messages, "temperature": 0, "max_tokens": 300,
                           "enable_thinking": False, "tools": [TOOL],
                           "tool_choice": {"type": "function", "function": {"name": "make_plan"}}}).encode()
        req = urllib.request.Request(BASE_URL, data=body, method="POST", headers={
            "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())

    def parse(self, text: str):
        """返回 (plan, source, latency_ms, cost_cny)。source ∈ llm / fallback"""
        messages = [{"role": "system", "content": _system()}, {"role": "user", "content": text}]
        h = hashlib.sha256(json.dumps([self.model, messages], ensure_ascii=False).encode()).hexdigest()
        cpath = self.cache_dir / f"{h}.json"
        resp, lat, cost = None, 0.0, 0.0
        if self.use_cache and cpath.exists():
            rec = json.loads(cpath.read_text(encoding="utf-8"))
            resp, lat = rec["resp"], rec["latency_ms"]
        elif self.key:
            _charge(0.0)
            t0 = time.perf_counter()
            for i in range(2):
                try:
                    resp = self._post(messages)
                    break
                except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
                    time.sleep(1.5)
            lat = (time.perf_counter() - t0) * 1000
            if resp is not None:
                cpath.write_text(json.dumps({"resp": resp, "latency_ms": lat}, ensure_ascii=False), encoding="utf-8")
                u = resp.get("usage") or {}
                c = cost_cny(self.model, u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
                _charge(c)
                with self._lock, open(DATA / "cost" / "llm.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "model": self.model, "purpose": "parse",
                                        "prompt_tokens": u.get("prompt_tokens", 0), "completion_tokens": u.get("completion_tokens", 0),
                                        "latency_ms": round(lat, 1), "req_hash": h[:16]}) + "\n")
        if resp is not None:
            u = resp.get("usage") or {}
            cost = cost_cny(self.model, u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        plan = None
        try:
            tc = resp["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
            plan = validate(json.loads(tc) if isinstance(tc, str) else tc)
        except Exception:
            plan = None
        with self._lock:
            self.stats["calls"] += 1
            self.stats["llm_ok" if plan else "fallback"] += 1
        if plan is None:
            return parse(text), "fallback", lat, cost
        return plan, "llm", lat, cost
