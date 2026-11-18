"""规则层：便宜、确定、毫秒级。

v1 = 开发者第一天照着接口文档就能写出来的规则：传输状态、字段/类型、物理范围、
新鲜度、回显一致性（请求的城市/日期/商户/菜品/金额是否被原样返回）、订单金额加总、
支付金额一致。跨字段的业务语义（晴天却有 30mm 降水、12km 配送 3 分钟）v1 不写，
这些交给 LLM；v2 演示「把 LLM 发现的 badcase 蒸馏成规则」（见 DISTILLED_V2）。

severity:
  hard  → 确定异常，直接走策略矩阵
  soft  → 可疑（如气温 -32°C、车费 221 元），规则拿不准：严格版当异常，宽松版放过，混合版交给 LLM 裁决
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .mock_apis import ToolResult
from . import world as W

NUM = (int, float)

SCHEMA = {
    "weather.query": {"city": str, "date": str, "condition": str, "temp_high_c": NUM, "temp_low_c": NUM, "updated_at": str},
    "weather_backup.query": {"city": str, "date": str, "condition": str, "temp_high_c": NUM, "temp_low_c": NUM},
    "food.search": {"restaurant": str, "items": list, "delivery_eta_min": NUM, "distance_km": NUM, "menu_updated_at": str},
    "food.order": {"order_id": str, "items": list, "total_cny": NUM},
    "pay.create": {"status": str, "amount_cny": NUM, "order_id": str},
    "pay.query": {"status": str},
    "map.route": {"distance_km": NUM, "duration_min": NUM},
    "ride.estimate": {"fare_cny": NUM, "distance_km": NUM, "pickup_eta_min": NUM},
}


@dataclass
class Flag:
    severity: str          # hard | soft
    type: str              # timeout | http_5xx | rate_limited | schema_error | semantic_wrong | context_mismatch | stale | partial | amount_mismatch | pay_status
    evidence: str


@dataclass
class RuleVerdict:
    flags: list = field(default_factory=list)

    @property
    def hard(self):
        return [f for f in self.flags if f.severity == "hard"]

    @property
    def soft(self):
        return [f for f in self.flags if f.severity == "soft"]


def _age_hours(s: str, now: datetime = W.NOW) -> Optional[float]:
    try:
        return (now - datetime.fromisoformat(s)).total_seconds() / 3600
    except Exception:
        return None


def check(r: ToolResult, request_ctx: dict, version: str = "v1") -> RuleVerdict:
    """失败即关闭（fail-closed）：规则本身抛异常（字段为 null、类型意外等）时，按 schema_error 硬异常处理，
    而不是让整条链路崩掉。这个缺口是独立生成集暴露的（降水为 null 导致比较报错）。"""
    try:
        return _check(r, request_ctx, version)
    except Exception as e:  # noqa: BLE001
        v = RuleVerdict()
        v.flags.append(Flag("hard", "schema_error", f"返回体无法校验（{type(e).__name__}），按不可信处理"))
        return v


def _check(r: ToolResult, request_ctx: dict, version: str = "v1") -> RuleVerdict:
    """request_ctx: 用户意图里的结构化槽位（city/date/restaurant/dish/items/amount 等），用于回显校验。"""
    v = RuleVerdict()
    add = lambda sev, t, ev: v.flags.append(Flag(sev, t, ev))
    if r.status == "timeout":
        add("hard", "timeout", f"{r.op} 超时 {r.latency_ms:.0f}ms")
        return v
    if r.status == "http_error":
        if r.http_code == 429:
            add("hard", "rate_limited", "HTTP 429")
        else:
            add("hard", "http_5xx", f"HTTP {r.http_code}")
        return v
    d = r.data or {}
    if "errcode" in d:
        return v   # 业务错误（如城市不支持）由 agent 如实告知，不算质量异常
    # ---- 字段与类型 ----
    for k, t in SCHEMA.get(r.op, {}).items():
        if k not in d:
            add("hard", "schema_error", f"缺少字段 {k}")
        elif not isinstance(d[k], t) or isinstance(d[k], bool):
            add("hard", "schema_error", f"字段 {k} 类型错误: {d[k]!r}")
    if v.hard:
        return v
    op = r.op
    if op in ("weather.query", "weather_backup.query"):
        hi, lo = d["temp_high_c"], d["temp_low_c"]
        for name, x in (("temp_high_c", hi), ("temp_low_c", lo)):
            if not -60 <= x <= 60:
                add("hard", "semantic_wrong", f"{name}={x} 超出物理范围")
            elif not -20 <= x <= 40:
                add("soft", "semantic_wrong", f"{name}={x} 少见")
        if lo > hi:
            add("hard", "semantic_wrong", f"最低温 {lo} > 最高温 {hi}")
        if d.get("precip_mm", 0) < 0:
            add("hard", "semantic_wrong", "降水量为负")
        if request_ctx.get("city") and d["city"] != request_ctx["city"]:
            add("hard", "context_mismatch", f"请求城市 {request_ctx['city']}，返回 {d['city']}")
        if request_ctx.get("date") and d["date"] != request_ctx["date"]:
            add("hard", "context_mismatch", f"请求日期 {request_ctx['date']}，返回 {d['date']}")
        if op == "weather.query":
            age = _age_hours(d["updated_at"], r.observed_at or W.NOW)
            if age is None:
                add("hard", "schema_error", "updated_at 无法解析")
            elif age > 24:
                add("hard", "stale", f"数据 {age:.0f} 小时前更新")
            elif age > 3:
                add("hard", "stale", f"数据 {age:.1f} 小时前更新（软过期）")
        if version == "v2" and d.get("condition") in ("晴", "多云") and d.get("precip_mm", 0) >= 1:
            add("hard", "semantic_wrong", f"[v2蒸馏] 天气「{d['condition']}」却有降水 {d['precip_mm']}mm")
    elif op == "food.search":
        if request_ctx.get("restaurant") and d["restaurant"] != request_ctx["restaurant"]:
            add("hard", "context_mismatch", f"请求商户 {request_ctx['restaurant']}，返回 {d['restaurant']}")
        if not d["items"]:
            add("hard", "partial", "菜单为空")
        for it in d["items"]:
            p = it.get("price_cny")
            if not isinstance(p, NUM) or isinstance(p, bool):
                add("hard", "schema_error", f"{it.get('name')} 价格类型错误: {p!r}")
                continue
            if p < 0:
                add("hard", "semantic_wrong", f"{it['name']} 价格为负")
            elif p == 0 and not any(s in it.get("name", "") + it.get("note", "") for s in ("赠", "免费")):
                add("soft", "semantic_wrong", f"{it['name']} 价格为 0")
            elif p > 200:
                add("soft", "semantic_wrong", f"{it['name']} 价格 {p} 偏高")
        eta = d["delivery_eta_min"]
        if eta < 0:
            add("hard", "semantic_wrong", f"配送时长 {eta} 为负")
        elif eta > 90:
            add("soft", "semantic_wrong", f"配送时长 {eta} 分钟偏长")
        if version == "v2" and eta > 0 and d["distance_km"] / (eta / 60) > 60:
            add("hard", "semantic_wrong", f"[v2蒸馏] {d['distance_km']}km 仅 {eta} 分钟，隐含时速超过 60km/h")
        age = _age_hours(d["menu_updated_at"])
        if age is not None and age > 24 * 7:
            add("hard", "stale", f"菜单 {age / 24:.0f} 天未更新")
        dish = request_ctx.get("dish")
        names = [it.get("name", "") for it in d["items"]]
        if d.get("has_more") and dish and not any(dish in n for n in names):
            add("hard", "partial", f"菜单分页未返回完整，且没有找到「{dish}」")
    elif op == "food.order":
        want = {i["name"]: int(i.get("qty", 1)) for i in request_ctx.get("items", [])}
        got = {i["name"]: int(i.get("qty", 0)) for i in d["items"]}
        if want and want != got:
            add("hard", "semantic_wrong", f"订单明细与请求不一致：请求 {want}，返回 {got}")
        s = round(sum(i.get("qty", 0) * i.get("price_cny", 0) for i in d["items"]), 2)
        if abs(s - d["total_cny"]) > 0.01:
            add("hard", "semantic_wrong", f"订单总价 {d['total_cny']} ≠ 明细加总 {s}")
        if d["total_cny"] > 300:
            add("soft", "semantic_wrong", f"订单金额 {d['total_cny']} 偏高")
    elif op == "pay.create":
        if d["status"] != "SUCCESS":
            add("hard", "pay_status", f"支付状态 {d['status']}")
        amt = request_ctx.get("amount_cny")
        if amt is not None and abs(d["amount_cny"] - amt) > 0.01:
            add("hard", "amount_mismatch", f"请求扣款 {amt}，实际 {d['amount_cny']}")
    elif op == "ride.estimate":
        if d["fare_cny"] <= 0:
            add("hard", "semantic_wrong", "车费非正")
        elif d["fare_cny"] > 200:
            add("soft", "semantic_wrong", f"车费 {d['fare_cny']} 偏高")
        if d["pickup_eta_min"] < 0:
            add("hard", "semantic_wrong", "接驾时间为负")
    elif op == "map.route":
        if d["distance_km"] < 0 or d["duration_min"] < 0:
            add("hard", "semantic_wrong", "距离/时长为负")
    return v
