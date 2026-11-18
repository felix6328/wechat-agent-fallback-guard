"""Agent 主循环：解析指令 → 调用工具 → 质检（规则层 / LLM）→ 策略矩阵决定 重试/降级/兜底/人工 → 回复。

对比变体：
  naive          无检测：传输失败时 SDK 式盲重试（不带幂等键），内容原样透传
  rules_lenient  仅规则，只认 hard 规则（soft 可疑放过）
  rules_strict   仅规则，hard + soft 都当异常（保守）
  hybrid         规则 hard 直接处置；soft 可疑与「规则全过」的返回交给 LLM 语义裁决；支付只走规则
  llm_only       传输层仍确定性处理；所有内容质检都交给 LLM（不跑内容规则）
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Optional

from .llm_judge import LLMJudge
from .backends.base import Backend
from .mock_apis import OP_TIER, ToolResult
from .parser import parse
from .paths import CONFIGS
from . import rules as R

POLICY = json.loads((CONFIGS / "policy.json").read_text(encoding="utf-8"))
TRANSPORT = {"timeout", "http_5xx", "rate_limited"}
PRIORITY = ["timeout", "http_5xx", "rate_limited", "schema_error", "amount_mismatch", "pay_status",
            "context_mismatch", "semantic_wrong", "stale", "stale_soft", "partial"]
LLM_OPS = {"weather.query", "weather_backup.query", "food.search", "food.order", "ride.estimate", "map.route"}
SEVERITY = {"ok": 0, "degraded": 1, "fallback": 2, "human": 3, "failed": 4}
VARIANTS = ["naive", "rules_lenient", "rules_strict", "hybrid", "llm_only"]


@dataclass
class Assessment:
    call_id: int
    op: str
    anomalous: bool
    type: str = "none"
    source: str = "none"       # rule | llm | transport | none
    evidence: str = ""
    llm_called: bool = False
    llm_failed: bool = False
    llm_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_cny: float = 0.0
    cache_hit: bool = False
    escalated: bool = False
    deferred: bool = False      # 展示类读：先展示，LLM 在后台复核
    is_async: bool = False
    pending_soft: list = field(default_factory=list)


@dataclass
class AgentResult:
    case_id: str
    variant: str
    plan: dict
    outcome: str = "ok"
    reply: str = ""
    shown: list = field(default_factory=list)          # [(call_id, caveat_bool)]
    assessments: list = field(default_factory=list)
    actions: list = field(default_factory=list)        # 人类可读的处置轨迹
    backoff_ms: float = 0.0
    corrected: list = field(default_factory=list)      # 异步复核后发出「更正」的 call_id
    parse_ms: float = 0.0
    parse_cost: float = 0.0
    parse_source: str = "wordlist"

    def bump(self, status: str):
        if SEVERITY[status] > SEVERITY[self.outcome]:
            self.outcome = status


class Agent:
    def __init__(self, variant: str, judge=None, rules_version: str = "v1",
                 llm_conf_threshold: float = 0.5, async_display: bool = False, verdict_cache=None,
                 llm_parser=None):
        """async_display：展示类读接口（查天气、看菜单、报价、路线）先展示、后台复核，发现问题再发更正；
        决策 / 写操作路径（叫车前的天气、下单前的菜单、订单）仍同步质检。
        verdict_cache：产品侧判定缓存（VerdictCache），命中时 0 时延 0 费用。
        llm_parser：LLM function calling 解析器（失败时回退词表）。"""
        assert variant in VARIANTS
        if variant in ("hybrid", "llm_only"):
            assert judge is not None, "hybrid / llm_only 需要 LLMJudge"
        self.variant, self.judge, self.rv, self.th = variant, judge, rules_version, llm_conf_threshold
        self.async_display, self.vcache, self.llm_parser = async_display, verdict_cache, llm_parser

    # ------------------------------------------------------------ 质检
    def assess(self, r: ToolResult, ctx: dict, instruction: str, defer: bool = False) -> Assessment:
        a = Assessment(r.call_id, r.op, False)
        self._defer = defer
        rv = R.check(r, ctx, self.rv)
        transport = [f for f in rv.hard if f.type in TRANSPORT]
        if transport:
            a.anomalous, a.type, a.source, a.evidence = True, transport[0].type, "transport", transport[0].evidence
            return a
        if self.variant == "naive" or (r.data or {}).get("errcode") is not None:
            return a
        if self.variant == "llm_only":
            if r.op in ("pay.query",):
                return a
            return self._ask_llm(a, r, ctx, instruction, [])
        hard = sorted(rv.hard, key=lambda f: PRIORITY.index(self._t(f)))
        if hard:
            f = hard[0]
            a.anomalous, a.type, a.source, a.evidence = True, self._t(f), "rule", f.evidence
            return a
        soft = rv.soft
        if self.variant == "rules_strict" and soft:
            a.anomalous, a.type, a.source, a.evidence = True, soft[0].type, "rule", "[soft] " + soft[0].evidence
            return a
        if self.variant == "hybrid" and r.op in LLM_OPS:
            return self._ask_llm(a, r, ctx, instruction, [f.evidence for f in soft], soft_fallback=soft)
        return a

    @staticmethod
    def _t(f):
        return "stale_soft" if f.type == "stale" and "软过期" in f.evidence else f.type

    def _ask_llm(self, a, r, ctx, instruction, soft_ev, soft_fallback=None):
        if getattr(self, "_defer", False):
            a.deferred, a.pending_soft = True, [soft_ev, soft_fallback]
            return a
        key = self.vcache.key(r.op, r.args, r.data, soft_ev) if self.vcache is not None else None
        v = self.vcache.get(key) if key else None
        a.llm_called = True
        if v is not None:
            a.cache_hit = True
            v = replace(v, latency_ms=0.0, cost_cny=0.0, prompt_tokens=0, completion_tokens=0)
        else:
            v = self.judge.judge(instruction, r.op, r.args, r.data or {}, soft_ev)
            if key and v is not None:
                self.vcache.put(key, v)
        if v is None:
            a.llm_failed = True
            if soft_fallback:   # LLM 挂了：对可疑项回退到保守规则
                a.anomalous, a.type, a.source, a.evidence = True, soft_fallback[0].type, "rule", "[LLM失败回退] " + soft_fallback[0].evidence
            return a
        a.llm_ms, a.prompt_tokens, a.completion_tokens = v.latency_ms, v.prompt_tokens, v.completion_tokens
        a.cost_cny, a.escalated = v.cost_cny, v.escalated
        if v.anomalous and v.confidence >= self.th:
            a.anomalous, a.type, a.source, a.evidence = True, (v.type if v.type != "none" else "semantic_wrong"), "llm", v.evidence
        elif soft_ev:
            a.evidence = "LLM 裁决放行：" + v.evidence
        return a

    # ------------------------------------------------------------ 主流程
    def run(self, instruction: str, env: Backend, case_id: str = "", input_plan: dict | None = None) -> AgentResult:
        src, pms, pcost = "wordlist", 0.0, 0.0
        if input_plan is not None:
            plan, src = input_plan, "structured"
        elif self.llm_parser is not None:
            plan, src, pms, pcost = self.llm_parser.parse(instruction)
        else:
            plan = parse(instruction)
        plan = env.prepare_plan(plan)
        res = AgentResult(case_id, self.variant, plan)
        res.parse_source, res.parse_ms, res.parse_cost = src, pms, pcost
        self.instruction, self.env, self.res = instruction, env, res
        intent = plan["intent"]
        try:
            if intent == "weather":
                self._weather(plan, final=True)
            elif intent == "food_menu":
                self._food_menu(plan)
            elif intent == "food_order":
                self._food_order(plan)
            elif intent == "ride":
                self._read_simple("ride.estimate", {"origin": plan["origin"], "dest": plan["dest"]}, {}, "打车")
            elif intent == "route":
                self._read_simple("map.route", {"origin": plan["origin"], "dest": plan["dest"], "mode": plan["mode"]}, {}, "路线")
            elif intent == "weather_ride":
                w = self._weather(plan, final=False)
                if w is not None and any(s in w.get("condition", "") for s in ("雨", "雪")):
                    res.reply += f" 有{w['condition']}，帮你查了车："
                    self._read_simple("ride.estimate", {"origin": plan["origin"], "dest": plan["dest"]}, {}, "打车")
                elif w is not None:
                    res.reply += " 不下雨，先不叫车。"
            else:
                res.reply = "没理解你的需求，可以换个说法吗？"
                res.bump("failed")
        except Exception as e:  # 防御：任何未预期错误都转人工，不给用户错误信息
            res.actions.append(f"未预期错误 {type(e).__name__}: {e}")
            res.reply = "处理出了点问题，请稍后再试。"
            res.bump("failed")
        return res

    def _call(self, op, args, ctx, defer=False) -> tuple[ToolResult, Assessment]:
        r = self.env.call(op, args)
        a = self.assess(r, ctx, self.instruction, defer=defer and self.async_display)
        self.res.assessments.append(a)
        tag = f"{a.type}（{a.source}：{a.evidence}）" if a.anomalous else ("正常" + (f"（{a.evidence}）" if a.evidence else ""))
        self.res.actions.append(f"#{r.call_id} {op} → {r.status} → {tag}")
        return r, a

    def _wait(self, kind, attempt):
        seq = POLICY["backoff_ms"].get(kind, POLICY["backoff_ms"]["default"])
        ms = seq[min(attempt, len(seq) - 1)]
        self.res.backoff_ms += ms
        wait = getattr(self.env, "wait", None)
        if wait is not None:
            wait(ms)
        self.res.actions.append(f"退避 {ms}ms 后重试")

    def _read_with_retry(self, op, args, ctx, defer=False):
        """读接口：传输类异常 → 退避重试；内容异常 → 交给调用方按矩阵处理。naive 不区分，盲重试。"""
        tier = OP_TIER[op]
        r, a = self._call(op, args, ctx, defer)
        tries = 0
        while a.anomalous and a.type in TRANSPORT and tries < POLICY["max_retries"][tier]:
            self._wait(a.type, tries)
            tries += 1
            r, a = self._call(op, args, ctx, defer)
        return r, a

    def _async_check(self, r, a, ctx) -> bool:
        """先展示后复核：在后台跑 LLM。返回 True 表示复核判异常（调用方要发更正）。"""
        if not a.deferred:
            return False
        self._defer = False
        soft_ev, soft_fb = a.pending_soft
        a.deferred, a.is_async = False, True
        self._ask_llm(a, r, ctx, self.instruction, soft_ev or [], soft_fallback=soft_fb)
        if a.anomalous:
            self.res.actions.append(f"后台复核 #{r.call_id} → {a.type}（{a.source}：{a.evidence}）→ 发出更正")
            self.res.corrected.append(r.call_id)
        else:
            self.res.actions.append(f"后台复核 #{r.call_id} → 正常")
        return a.anomalous

    def _action(self, op, typ):
        return POLICY["matrix"][OP_TIER[op] if op != "weather_backup.query" else "read"].get(typ, "fallback")

    # ------------------------------------------------------------ 天气
    def _weather(self, plan, final=True) -> Optional[dict]:
        args = {"city": plan["city"], "date": plan["date"]}
        r, a = self._read_with_retry("weather.query", args, args, defer=final)
        if not a.anomalous:
            if (r.data or {}).get("errcode"):
                self.res.reply = f"暂不支持查询{plan['city']}的天气。"
                return None
            self._say_weather(r, caveat=None)
            if not self._async_check(r, a, args):
                return r.data
            first = self.res.reply
            self._weather_fix(plan, args, r, a)
            self.res.reply = first + " 【更正】" + self.res.reply
            return None
        if self.variant == "naive":
            self.res.reply = "天气服务暂时不可用，请稍后再试。"
            self.res.bump("failed")
            return None
        return self._weather_fix(plan, args, r, a)

    def _weather_fix(self, plan, args, r, a):
        act = self._action("weather.query", a.type)
        if act == "degrade":
            self.res.actions.append("策略：降级展示，并注明数据更新时间")
            self._say_weather(r, caveat=f"（注意：该数据更新于 {r.data['updated_at']}，可能不是最新）")
            self.res.bump("degraded")
            return r.data
        if not getattr(self.env, "has_weather_backup", True):
            self.res.reply = f"{plan['city']}的天气数据暂时不可靠，请查阅当地气象预报。"
            self.res.actions.append("策略：暂停展示异常天气，提示核对当地预报")
            self.res.bump("fallback")
            return None
        # fallback：备用气象源
        self.res.actions.append("策略：切换备用气象源")
        b, ba = self._read_with_retry("weather_backup.query", args, args)
        if not ba.anomalous and not (b.data or {}).get("errcode"):
            self._say_weather(b, caveat="（主数据源异常，以下来自备用气象源，粒度较粗）")
            self.res.bump("fallback")
            return b.data
        self.res.reply = f"{plan['city']}的天气数据暂时不可靠，已为你打开天气小程序页面，请以页面为准。"
        self.res.actions.append("策略：备用源也异常 → 页面接力")
        self.res.bump("fallback")
        return None

    def _say_weather(self, r, caveat):
        d = r.data
        txt = f"{d['city']} {d['date']}：{d['condition']}，{d['temp_low_c']}~{d['temp_high_c']}°C"
        if "precip_mm" in d:
            txt += f"，降水 {d['precip_mm']}mm"
        if r.observed_at is not None:
            txt += f"（{d.get('source', '天气服务')}，发布于 {d.get('updated_at', '未知')}）"
        self.res.reply = txt + (caveat or "")
        self.res.shown.append((r.call_id, bool(caveat)))

    # ------------------------------------------------------------ 打车 / 地图（读）
    def _read_simple(self, op, args, ctx, label):
        r, a = self._read_with_retry(op, args, ctx, defer=True)
        if not a.anomalous:
            d = r.data
            if op == "ride.estimate":
                self.res.reply += f"{d['origin']}→{d['dest']} 快车约 {d['fare_cny']} 元，{d['pickup_eta_min']} 分钟接驾。确认后再下单。"
            else:
                self.res.reply += f"{d['origin']}→{d['dest']} {d['distance_km']}km，约 {d['duration_min']} 分钟。"
            self.res.shown.append((r.call_id, False))
            if not self._async_check(r, a, ctx):
                return d
            self.res.reply += f" 【更正】{label}信息可能不准，已为你打开对应小程序页面，请以页面为准。"
            self.res.bump("fallback")
            return None
        if self.variant == "naive":
            self.res.reply += f"{label}服务暂时不可用。"
            self.res.bump("failed")
            return None
        self.res.reply += f"{label}信息暂时不可靠，已为你打开对应小程序页面，请在页面里确认。"
        self.res.actions.append("策略：页面接力")
        self.res.bump("fallback")
        return None

    # ------------------------------------------------------------ 外卖
    def _search(self, plan, defer=False):
        args = {"restaurant": plan["restaurant"]}
        if plan.get("dish"):
            args["dish"] = plan["dish"]
        ctx = {"restaurant": plan["restaurant"], "dish": plan.get("dish")}
        return self._read_with_retry("food.search", args, ctx, defer)

    def _food_menu(self, plan):
        r, a = self._search(plan, defer=True)
        if not a.anomalous:
            d = r.data
            if d.get("errcode"):
                self.res.reply = "没找到这家店。"
                return
            items = "、".join(f"{i['name']}¥{i['price_cny']}" for i in d["items"])
            self.res.reply = f"{d['restaurant']}：{items}；约 {d['delivery_eta_min']} 分钟送达。"
            self.res.shown.append((r.call_id, False))
            if not self._async_check(r, a, {"restaurant": plan["restaurant"], "dish": plan.get("dish")}):
                return
            first = self.res.reply
            self._food_menu_fix(plan, r, a)
            self.res.reply = first + " 【更正】" + self.res.reply
            return
        if self.variant == "naive":
            self.res.reply = "外卖服务暂时不可用，请稍后再试。"
            self.res.bump("failed")
            return
        self._food_menu_fix(plan, r, a)

    def _food_menu_fix(self, plan, r, a):
        act = self._action("food.search", a.type)
        if a.type in ("partial", "stale"):
            act = "degrade"
        if act == "degrade":
            d = r.data
            items = "、".join(f"{i['name']}¥{i['price_cny']}" for i in d["items"])
            note = "菜单只加载了一部分" if a.type == "partial" else f"菜单更新于 {d['menu_updated_at']}，价格可能已变"
            self.res.reply = f"{d['restaurant']}：{items}（{note}，点卡片进小程序看完整/最新菜单）"
            self.res.shown.append((r.call_id, True))
            self.res.actions.append("策略：降级展示 + 页面接力卡片")
            self.res.bump("degraded")
            return
        self.res.reply = f"{plan['restaurant']}的菜单信息暂时不可靠，已为你打开外卖小程序页面。"
        self.res.actions.append("策略：不展示可疑数据，页面接力")
        self.res.bump("fallback")

    def _food_order(self, plan):
        dish = plan["items"][0]["name"].split("（")[0]
        r, a = self._search({**plan, "dish": dish})
        if a.anomalous and self.variant != "naive":
            act = "degrade" if a.type in ("stale",) else self._action("food.search", a.type)
            if act != "degrade":
                self.res.reply = "菜品信息异常，先不帮你下单，已打开外卖小程序页面请你确认。"
                self.res.actions.append("策略：查询结果异常，不下单，页面接力")
                self.res.bump("fallback")
                return
            self.res.actions.append("策略：菜单过期，继续下单但以订单价格为准")
            self.res.shown.append((r.call_id, True))
            self.res.bump("degraded")
        elif a.anomalous:
            self.res.reply = "外卖服务暂时不可用。"
            self.res.bump("failed")
            return
        else:
            self.res.shown.append((r.call_id, False))   # 下单前会把菜品和价格展示给用户
        # ---- 下单（写操作）----
        token = None if self.variant == "naive" else f"tok-{self.env.case_id}"
        oargs = {"restaurant": plan["restaurant"], "items": plan["items"]}
        if token:
            oargs["client_token"] = token
        octx = {"items": plan["items"]}
        o, oa = self._call("food.order", oargs, octx)
        tries = 0
        while oa.anomalous and oa.type in TRANSPORT and tries < POLICY["max_retries"]["write"]:
            self._wait(oa.type, tries)
            tries += 1
            o, oa = self._call("food.order", oargs, octx)
        if oa.anomalous:
            if self.variant == "naive":
                self.res.reply = "下单失败，请稍后再试。"
                self.res.bump("failed")
                return
            if oa.type in TRANSPORT:
                self.res.reply = "下单结果暂时无法确认，没有扣款。请在外卖小程序「订单」页确认，避免重复下单。"
            else:
                self.res.reply = f"订单信息和你的要求不一致（{oa.evidence}），没有付款，请确认后再继续。"
            self.res.actions.append("策略：写操作异常 → 转用户确认，不进入支付")
            self.res.bump("human")
            return
        od = o.data
        self.res.shown.append((o.call_id, False))
        if not plan.get("pay"):
            self.res.reply = f"已下单 {od['order_id']}，共 {od['total_cny']} 元，待支付。"
            return
        self._pay(od)

    # ------------------------------------------------------------ 支付（永不盲重试）
    def _pay(self, od):
        start_payment = getattr(self.env, "start_payment", None)
        if start_payment is not None:
            trade, trace = start_payment(od)
            self.res.actions.extend(f"沙箱：{action}" for action in trace)
            if trade is None:
                self.res.reply = "模拟外卖订单已创建。启用支付宝沙箱后可测试付款。"
                self.res.bump("human")
            elif trade.state == "PAID":
                self.res.reply = f"支付宝沙箱查单确认已支付 {trade.amount} 元。"
            elif trade.state == "PENDING" and trade.checkout:
                self.res.reply = f"沙箱收银台已就绪，待你付款 {trade.amount} 元：{trade.checkout}"
                self.res.bump("human")
            else:
                self.res.reply = "沙箱订单待核对，请先查单并核对金额。"
                self.res.bump("human")
            return
        amount = od["total_cny"]
        key = None if self.variant == "naive" else f"pay-{od['order_id']}"
        pargs = {"order_id": od["order_id"], "amount_cny": amount}
        if key:
            pargs["idempotency_key"] = key
        pctx = {"amount_cny": amount}
        p, pa = self._call("pay.create", pargs, pctx)
        if self.variant == "naive":
            tries = 0
            while pa.anomalous and tries < 2:      # 典型 SDK 重试：同样的请求再发一次，没有幂等键
                self._wait(pa.type, tries)
                tries += 1
                p, pa = self._call("pay.create", pargs, pctx)
            if pa.anomalous:
                self.res.reply = "支付失败，请稍后再试。"
                self.res.bump("failed")
                return
            self.res.reply = f"已支付 {p.data['amount_cny']} 元，订单 {od['order_id']}。"
            self.res.shown.append((p.call_id, False))
            return
        if not pa.anomalous:
            self.res.reply = f"已支付 {p.data['amount_cny']} 元，订单 {od['order_id']}。"
            self.res.shown.append((p.call_id, False))
            return
        act = POLICY["matrix"]["pay"].get(pa.type, "human")
        if act == "query_status_then_decide":
            self.res.actions.append("策略：支付结果未知 → 先按幂等键查单，不直接重试")
            q, qa = self._call("pay.query", {"idempotency_key": key}, {})
            st = (q.data or {}).get("status") if not qa.anomalous else None
            if st == "SUCCESS" and abs(q.data["amount_cny"] - amount) < 0.01:
                self.res.reply = f"支付已成功（查单确认），{q.data['amount_cny']} 元，订单 {od['order_id']}。"
                self.res.shown.append((q.call_id, False))
                return
            if st == "NOT_FOUND":
                self.res.actions.append("查单：未扣款 → 用同一幂等键重试一次（服务端去重，不会重复扣）")
                self._wait("default", 0)
                p2, pa2 = self._call("pay.create", pargs, pctx)
                if not pa2.anomalous:
                    self.res.reply = f"已支付 {p2.data['amount_cny']} 元，订单 {od['order_id']}。"
                    self.res.shown.append((p2.call_id, False))
                    return
            self.res.reply = "支付结果确认中，请勿重复支付。支付结果会通过支付平台通知你，如有疑问可联系客服。"
            self.res.actions.append("策略：查单无法确认 → 转人工/等待通知，绝不再发起扣款")
            self.res.bump("human")
            return
        self.res.reply = f"支付金额异常（{pa.evidence}），已暂停并转人工客服核实，如多扣会原路退回。"
        self.res.actions.append("策略：资金异常 → 人工")
        self.res.bump("human")
