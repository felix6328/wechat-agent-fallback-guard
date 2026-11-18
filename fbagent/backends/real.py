"""Real weather responses with faults applied after the provider call."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from time import perf_counter, sleep

from .. import world as W
from ..mock_apis import Env, ToolResult
from ..payment import Recovery, SandboxPayment, order_number, reserve_order
from ..paths import ROOT
from .alipay import Trade, parse_amount
from .amap import AmapClient
from .base import ProviderFailure

WEATHER_FAULTS = {
    "sem_city", "sem_range_temp", "sem_inrange_temp", "sem_condition_season",
    "schema_missing", "stale_soft", "stale_hard", "http_429", "http_500", "timeout",
}


@dataclass
class RealEnv(Env):
    has_weather_backup = False

    amap: AmapClient | None = None
    sandbox: SandboxPayment | None = None
    observed_at: datetime | None = None

    def __post_init__(self):
        super().__post_init__()
        if self.observed_at is None:
            self.observed_at = datetime.now(W.TZ)

    def prepare_plan(self, plan: dict) -> dict:
        if plan.get("intent") not in {"weather", "weather_ride"} or "date" not in plan:
            return plan
        if plan.get("live_date"):
            return plan
        mock_day = W.NOW.date()
        offset = datetime.fromisoformat(plan["date"]).date() - mock_day
        if plan["date"] in W.DATES.values():
            return {**plan, "date": (self.observed_at.date() + offset).isoformat()}
        return plan

    def start_payment(self, order: dict) -> tuple[Trade | None, list[str]]:
        if self.sandbox is None:
            return None, []
        order_no = order_number(self.case_id, order["order_id"])
        amount = parse_amount(order["total_cny"])
        reserve_order(ROOT / "cache/alipay/orders.sqlite", order_no, amount, "page")
        recovery = Recovery(self.sandbox, order_no, amount)
        trade = recovery.start()
        return trade, recovery.trace

    @staticmethod
    def wait(milliseconds: float) -> None:
        sleep(milliseconds / 1000)

    def call(self, op: str, args: dict) -> ToolResult:
        if op == "weather_backup.query":
            return self._finish(op, args, None, "ok", 200,
                                {"errcode": 503, "errmsg": "真实天气演示无独立备用数据源"}, 0)
        if op != "weather.query":
            return super().call(op, args)
        if self.amap is None:
            raise ValueError("真实天气接口需要 AMAP_KEY")
        fault = self._next_fault(op)
        if fault and (not isinstance(fault, str) or fault not in WEATHER_FAULTS):
            raise ValueError("真实天气后端不支持该注入类型")
        started = perf_counter()
        try:
            data = self.amap.forecast(args["city"], args["date"])
        except ProviderFailure as exc:
            latency = (perf_counter() - started) * 1000
            if exc.status == 404:
                return self._finish(op, args, None, "ok", 200,
                                    {"errcode": 404, "errmsg": exc.reason}, latency)
            return self._finish(op, args, None, "http_error" if exc.status else "timeout",
                                exc.status, {"provider_error": exc.reason}, latency)
        latency = (perf_counter() - started) * 1000
        if fault in {"timeout", "http_500", "http_429"}:
            code = {"timeout": 0, "http_500": 500, "http_429": 429}[fault]
            return self._finish(op, args, fault, "http_error" if code else "timeout", code, None, latency)
        data = inject_weather(data, fault, self.observed_at, self.rng)
        result = self._finish(op, args, fault, "ok", 200, data, latency)
        result.observed_at = self.observed_at
        return result


def inject_weather(data: dict, fault: str | None, now: datetime, rng) -> dict:
    result = data.copy()
    if fault == "sem_city":
        result["city"] = "上海" if data["city"] != "上海" else "广州"
    elif fault == "sem_range_temp":
        result["temp_high_c"] = rng.choice((78, 82, 86))
    elif fault == "sem_inrange_temp":
        low = rng.choice((-17, -16, -15))
        result.update(temp_low_c=low, temp_high_c=low + 8)
    elif fault == "sem_condition_season":
        result["condition"] = "大雪" if data["condition"] != "大雪" else "晴"
    elif fault == "schema_missing":
        result.pop("condition", None)
    elif fault in {"stale_soft", "stale_hard"}:
        result["updated_at"] = (now - timedelta(hours=5 if fault == "stale_soft" else 72)).isoformat()
    return result
