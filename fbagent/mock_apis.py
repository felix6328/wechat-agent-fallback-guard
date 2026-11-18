"""5 个模拟小程序原子接口 + 可配置故障注入（固定种子，可复现）。

服务：打车 ride、外卖 food、天气 weather、支付 pay、地图 map。
只有 food / weather / pay 三个服务允许注入故障；ride、map 永远健康，作为误报对照。
另有 weather_backup（备用气象源，永远健康，字段更粗）供兜底使用。

Agent 只能看到 ToolResult；每次调用的故障真值记录在 Env.gt，只供评测器读取。
时延是「虚拟时延」（按种子抽样的毫秒数，不真的 sleep），超时按超时预算计入。
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from . import world as W

FAULTABLE = {"weather.query", "food.search", "food.order", "pay.create", "pay.query"}
TIMEOUT_MS = {"read": 2000, "write": 3000, "pay": 3000}
OP_TIER = {
    "weather.query": "read", "weather_backup.query": "read", "food.search": "read",
    "map.route": "read", "ride.estimate": "read",
    "food.order": "write", "pay.create": "pay", "pay.query": "read",
}
BASE_LATENCY_MS = {
    "weather.query": 180, "weather_backup.query": 260, "food.search": 380, "food.order": 450,
    "pay.create": 600, "pay.query": 220, "map.route": 240, "ride.estimate": 320,
}

# 「数据错了」类故障：即使附带免责声明展示给用户，也算暴露
WRONG_DATA_KINDS = {
    "schema_missing", "schema_type", "sem_range_temp", "sem_low_gt_high", "sem_city",
    "sem_condition_precip", "sem_inrange_temp", "sem_condition_season", "sem_price_zero",
    "sem_price_unit", "sem_eta_negative", "sem_eta_implausible", "sem_wrong_menu",
    "sem_qty", "amount_mismatch",
}
WRONG_DATA_KINDS |= {"gen_wrong"}          # 独立生成集：错误数据
# 「旧/缺」类故障：带明确提示的降级展示不算暴露
DISCLOSABLE_KINDS = {"stale_hard", "stale_soft", "stale_menu", "partial", "gen_stale", "gen_partial"}
TRANSPORT_KINDS = {"timeout", "http_500", "http_429", "timeout_after_charge",
                   "timeout_before_charge", "timeout_after_create", "processing"}


@dataclass
class ToolResult:
    call_id: int
    op: str
    args: dict
    status: str               # ok | timeout | http_error
    http_code: int = 200
    latency_ms: float = 0.0
    data: Optional[dict] = None
    observed_at: datetime | None = None

    def brief(self) -> dict:
        return {"call_id": self.call_id, "op": self.op, "args": self.args, "status": self.status,
                "http_code": self.http_code, "latency_ms": round(self.latency_ms, 1), "data": self.data}


@dataclass
class Env:
    case_id: str
    fault_plan: dict = field(default_factory=dict)
    seed: int = 42
    random_faults: Optional[dict] = None   # configs/faults.json 内容；给定则按概率随机注入

    def __post_init__(self):
        h = int(hashlib.sha256(f"{self.seed}:{self.case_id}".encode()).hexdigest()[:12], 16)
        self.rng = random.Random(h)
        self.plan = {k: list(v) for k, v in (self.fault_plan or {}).items()}
        for op, specs in self.plan.items():
            for sp in specs:
                kind = sp.get("kind") if isinstance(sp, dict) else sp
                # gen_clean = 用「看着怪但正确」的数据替换返回（难负例），任何接口都允许；真正的故障只允许 3 个服务
                if op not in FAULTABLE and kind not in ("ok", "gen_clean"):
                    raise ValueError(f"只有 food/weather/pay 可注入故障，非法: {op}")
        self.calls: list[ToolResult] = []
        self.gt: dict[int, Optional[str]] = {}
        self.payments: dict[str, list[dict]] = {}   # order_id -> charges
        self.pay_keys: dict[str, dict] = {}         # idempotency_key -> charge
        self.orders: list[dict] = []
        self.order_tokens: dict[str, dict] = {}
        self.virtual_ms = 0.0

    def prepare_plan(self, plan: dict) -> dict:
        return plan

    # ---------------- 故障选择 ----------------
    def _next_fault(self, op: str):
        if op in self.plan and self.plan[op]:
            k = self.plan[op].pop(0)
            return None if k == "ok" else k
        if self.random_faults and op in self.random_faults.get("kinds", {}):
            if self.rng.random() < self.random_faults["per_call_fault_rate"]:
                kinds = self.random_faults["kinds"][op]
                names, weights = zip(*kinds.items())
                return self.rng.choices(names, weights=weights)[0]
        return None

    def _latency(self, op: str) -> float:
        return BASE_LATENCY_MS[op] * self.rng.lognormvariate(0, 0.25)

    def _finish(self, op, args, fault, status, code, data, latency) -> ToolResult:
        self.virtual_ms += latency
        r = ToolResult(len(self.calls), op, copy.deepcopy(args), status, code, latency,
                       copy.deepcopy(data) if data is not None else None)
        self.calls.append(r)
        self.gt[r.call_id] = fault
        return r

    def call(self, op: str, args: dict) -> ToolResult:
        fault = self._next_fault(op) if (op in FAULTABLE or op in self.plan) else None
        tier = OP_TIER[op]
        lat = self._latency(op)
        if isinstance(fault, dict):
            # 独立生成集：整段替换返回体。gen_clean 是难负例，真值为无故障
            kind = fault["kind"]
            data = copy.deepcopy(fault["data"])
            return self._finish(op, args, None if kind == "gen_clean" else kind, "ok", 200, data, lat)
        if fault in ("timeout", "timeout_before_charge"):
            return self._finish(op, args, fault, "timeout", 0, None, TIMEOUT_MS[tier])
        if fault == "http_500":
            return self._finish(op, args, fault, "http_error", 500, {"errcode": 500, "errmsg": "internal error"}, lat)
        if fault == "http_429":
            return self._finish(op, args, fault, "http_error", 429, {"errcode": 429, "errmsg": "too many requests"}, lat)
        handler = getattr(self, "_" + op.replace(".", "_"))
        data = handler(args, fault)
        if fault in ("timeout_after_charge", "timeout_after_create"):
            # 服务端已经执行（扣款/下单），但响应在网络上丢了
            return self._finish(op, args, fault, "timeout", 0, None, TIMEOUT_MS[tier])
        return self._finish(op, args, fault, "ok", 200, data, lat)

    # ---------------- 天气 ----------------
    def _weather_truth(self, args):
        city, date = args.get("city"), args.get("date")
        base = W.WEATHER.get(city)
        if base is None:
            return None
        d = dict(base)
        return {"city": city, "date": date, **d,
                "updated_at": W.ts(W.NOW - timedelta(minutes=self.rng.randint(10, 55))),
                "source": "小程序A·气象服务"}

    def _weather_query(self, args, fault):
        d = self._weather_truth(args)
        if d is None:
            return {"errcode": 404, "errmsg": "city not supported"}
        if fault == "schema_missing":
            d.pop(self.rng.choice(["temp_high_c", "condition"]))
        elif fault == "schema_type":
            d["temp_high_c"] = f"{d['temp_high_c']}度"
        elif fault == "sem_range_temp":
            d["temp_high_c"] = self.rng.choice([78, 80, 85])
        elif fault == "sem_low_gt_high":
            d["temp_low_c"], d["temp_high_c"] = d["temp_high_c"] + 3, d["temp_low_c"]
        elif fault == "sem_city":
            d["city"] = self.rng.choice([c for c in W.WEATHER if c != args.get("city")])
        elif fault == "sem_condition_precip":
            d["condition"], d["precip_mm"] = "晴", round(self.rng.uniform(22, 35), 1)
        elif fault == "sem_inrange_temp":
            # 城市对、字段齐、数值在通用范围内，但对该城市该季节明显不对（像串了北方城市的数据）
            d["temp_high_c"], d["temp_low_c"] = -9, -17
        elif fault == "sem_condition_season":
            d["condition"] = "大雪"
        elif fault == "stale_hard":
            d["updated_at"] = W.ts(W.NOW - timedelta(days=3, minutes=self.rng.randint(0, 120)))
        elif fault == "stale_soft":
            d["updated_at"] = W.ts(W.NOW - timedelta(hours=5, minutes=self.rng.randint(0, 40)))
        return d

    def _weather_backup_query(self, args, fault):
        d = self._weather_truth(args)
        if d is None:
            return {"errcode": 404, "errmsg": "city not supported"}
        d.pop("precip_mm", None)
        d["source"] = "备用气象源（粗粒度，无降水量）"
        d["updated_at"] = W.ts(W.NOW - timedelta(minutes=70))
        return d

    # ---------------- 外卖 ----------------
    def _food_search(self, args, fault):
        name = args.get("restaurant")
        r = W.RESTAURANTS.get(name)
        if r is None:
            return {"errcode": 404, "errmsg": "restaurant not found"}
        d = {"restaurant": name, "items": copy.deepcopy(r["items"]), "has_more": False,
             "distance_km": r["distance_km"], "delivery_eta_min": r["delivery_eta_min"],
             "note": r["note"], "menu_updated_at": W.ts(W.NOW - timedelta(hours=2))}
        main = 0  # 第一个是主推菜
        if fault == "schema_type":
            d["items"][main]["price_cny"] = "二十五元八角"
        elif fault == "sem_price_zero":
            d["items"][main]["price_cny"] = 0.0
        elif fault == "sem_price_unit":
            d["items"][main]["price_cny"] = round(d["items"][main]["price_cny"] * 10, 1)
        elif fault == "sem_eta_negative":
            d["delivery_eta_min"] = -self.rng.randint(3, 15)
        elif fault == "sem_eta_implausible":
            d["distance_km"], d["delivery_eta_min"] = 12.4, 3
        elif fault == "sem_wrong_menu":
            d["items"] = [{"name": "巨无霸套餐", "price_cny": 39.0}, {"name": "麦辣鸡翅", "price_cny": 13.5},
                          {"name": "麦旋风", "price_cny": 12.0}]
        elif fault == "stale_menu":
            d["menu_updated_at"] = W.ts(W.NOW - timedelta(days=40))
        elif fault == "partial":
            d["items"] = d["items"][-1:]
            d["has_more"] = True
            d["total_items"] = len(r["items"]) + 30
        return d

    def _food_order(self, args, fault):
        token = args.get("client_token")
        if token and token in self.order_tokens:
            return copy.deepcopy(self.order_tokens[token])   # 幂等：同 token 返回原订单
        r = W.RESTAURANTS[args["restaurant"]]
        price = {i["name"]: i["price_cny"] for i in r["items"]}
        items = [{"name": it["name"], "qty": int(it.get("qty", 1)), "price_cny": price[it["name"]]}
                 for it in args["items"]]
        if fault == "sem_qty":
            items[0]["qty"] = items[0]["qty"] * 10
        total = round(sum(i["qty"] * i["price_cny"] for i in items), 2)
        order = {"order_id": f"FO{len(self.orders) + 1:04d}-{self.case_id}", "restaurant": args["restaurant"],
                 "items": items, "total_cny": total, "status": "CREATED", "eta_min": r["delivery_eta_min"]}
        self.orders.append(order)
        if token:
            self.order_tokens[token] = order
        return order

    # ---------------- 支付 ----------------
    def _pay_create(self, args, fault):
        key = args.get("idempotency_key")
        if key and key in self.pay_keys:
            return copy.deepcopy(self.pay_keys[key])         # 幂等：同 key 不重复扣款
        amount = float(args["amount_cny"])
        charged = round(amount * 10, 2) if fault == "amount_mismatch" else amount
        ch = {"pay_id": f"PAY{sum(len(v) for v in self.payments.values()) + 1:04d}", "order_id": args["order_id"],
              "amount_cny": charged, "status": "SUCCESS"}
        self.payments.setdefault(args["order_id"], []).append(ch)
        if key:
            self.pay_keys[key] = ch
        return ch

    def _pay_query(self, args, fault):
        if fault == "processing":
            return {"status": "PROCESSING", "idempotency_key": args.get("idempotency_key")}
        ch = self.pay_keys.get(args.get("idempotency_key"))
        if ch is None:
            return {"status": "NOT_FOUND", "idempotency_key": args.get("idempotency_key")}
        return {**copy.deepcopy(ch), "idempotency_key": args.get("idempotency_key")}

    # ---------------- 地图 / 打车（健康服务） ----------------
    def _map_route(self, args, fault):
        r = W.route(args["origin"], args["dest"])
        mode = args.get("mode", "drive")
        return {"origin": args["origin"], "dest": args["dest"], "mode": mode, "distance_km": r["distance_km"],
                "duration_min": r["walk_min"] if mode == "walk" else r["drive_min"]}

    def _ride_estimate(self, args, fault):
        r = W.route(args["origin"], args["dest"])
        return {"origin": args["origin"], "dest": args["dest"], "car_type": "快车", "distance_km": r["distance_km"],
                "fare_cny": W.ride_fare(r["distance_km"], r["drive_min"]), "pickup_eta_min": self.rng.randint(2, 8),
                "quote_id": f"Q-{self.case_id}", "note": "需用户确认后下单"}

    # ---------------- 评测器专用 ----------------
    def harm(self) -> dict:
        dup_charge = any(len(v) > 1 for v in self.payments.values())
        dup_order = len(self.orders) > len({(o["restaurant"], json.dumps(
            [(i["name"]) for i in o["items"]], ensure_ascii=False)) for o in self.orders})
        return {"duplicate_charge": dup_charge, "duplicate_order": dup_order,
                "n_charges": sum(len(v) for v in self.payments.values()), "n_orders": len(self.orders)}


def load_fault_config(path: Optional[Path] = None) -> dict:
    from .paths import CONFIGS
    return json.loads((path or CONFIGS / "faults.json").read_text(encoding="utf-8"))
