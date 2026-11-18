"""Collect real forecasts once and compare variants on the same frozen responses."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
from time import perf_counter, sleep

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fbagent.backends.amap import AmapClient  # noqa: E402
from fbagent.backends.base import ProviderFailure  # noqa: E402
from fbagent.backends.real import RealEnv  # noqa: E402
from fbagent.payment import PAID_RESPONSE_DROPPED  # noqa: E402
from fbagent.envload import load_setting  # noqa: E402
from fbagent.evaluate import pct, run_case  # noqa: E402
from fbagent.llm_judge import LLMJudge  # noqa: E402
from fbagent.world import TZ  # noqa: E402


class RecordedAmap:
    def __init__(self, snapshots: dict):
        self.snapshots = snapshots

    def forecast(self, city: str, date: str) -> dict:
        return self.snapshots[(city, date)]["weather"]


class EvalEnv(RealEnv):
    @staticmethod
    def wait(milliseconds: float) -> None:
        """Represent the backoff in the output latency without sleeping during replay."""


def capture(client: AmapClient, cases: list[dict], now: datetime):
    snapshots, errors = {}, {}
    for sample in cases:
        city = sample["city"]
        date = (now.date() + timedelta(days=sample["day_offset"])).isoformat()
        stamp = (city, date)
        if stamp in snapshots or stamp in errors:
            continue
        start = perf_counter()
        count = client.request_count
        for attempt in range(2):
            try:
                weather = client.forecast(city, date)
                break
            except ProviderFailure as exc:
                if attempt == 0 and exc.status in {0, 500, 502, 503, 504}:
                    sleep(0.35)
                    continue
                errors[stamp] = exc.reason
                break
        if stamp in errors:
            continue
        snapshots[stamp] = {
            "weather": weather, "capture_ms": round((perf_counter() - start) * 1000, 1),
            "network_requests": client.request_count - count,
        }
    return snapshots, errors


def evaluate(cases, seeds, snapshots, now, judge):
    rows = []
    backend = RecordedAmap(snapshots)
    variants = [("naive", None), ("rules_strict", None)]
    if judge:
        variants.append(("hybrid", judge))
    for variant, active_judge in variants:
        for sample in cases:
            city, fault = sample["city"], sample["fault"]
            date = (now.date() + timedelta(days=sample["day_offset"])).isoformat()
            if (city, date) not in snapshots:
                continue
            plan = {"intent": "weather", "city": city, "date": date, "live_date": True}
            faults = {"weather.query": [fault]} if fault else {}
            case = {**sample, "input_plan": plan, "fault_plan": faults}
            for seed in seeds:
                env = EvalEnv(sample["id"], faults, seed=seed, amap=backend, observed_at=now)
                row = run_case(case, variant, active_judge, seed=seed, env=env)
                row["capture_ms"] = snapshots[(city, date)]["capture_ms"]
                row["fault"] = fault
                rows.append(row)
        print(f"完成 {variant}", flush=True)
    return rows


def summarize(rows: list[dict]) -> dict:
    clean = [row for row in rows if not row["fault"]]
    harm = [row for row in rows if row["exposure"] or row["harmful"]]
    false_alarms = sum(any(call["pred"] for call in row["calls"]) for row in clean)
    lat = [row["latency_ms"] for row in rows]
    return {"samples": len(rows), "clean_samples": len(clean), "harm": len(harm),
            "false_alarms": false_alarms, "failed": sum(row["outcome"] == "failed" for row in rows),
            "decision_p50_ms": pct(lat, 50), "decision_p95_ms": pct(lat, 95),
            "model_failures": sum(row["llm_failed"] for row in rows),
            "cost_cny": sum(row["cost_cny"] for row in rows)}


def payment_status(path: Path) -> dict:
    rows = ([json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
            if path.is_file() else [])
    trade_by_order = {}
    verified_orders = set()
    closed_trades = {}
    for row in rows:
        if row["state"] in ("PAID", "REFUNDED") and row["trade_no"]:
            trade_by_order.setdefault(row["order_no"], set()).add(row["trade_no"])
        if row["action"] == "close" and row["state"] == "CLOSED":
            closed_trades[row["order_no"]] = row["trade_no"]
        if row["action"] == "verify" and row["state"] == "PAID" and row["trade_no"]:
            trace = row["trace"]
            if row["dropped_paid_response"] and trace.count(PAID_RESPONSE_DROPPED) == 1:
                fault = trace.index(PAID_RESPONSE_DROPPED)
                if 0 < fault < len(trace) - 1 and all(
                    step == "trade.query" for step in trace[:fault] + trace[fault + 1:]
                ):
                    verified_orders.add(row["order_no"])
    return {"verified": bool(verified_orders), "orders": len(trade_by_order),
            "duplicate_trade_orders": (sum(len(ids) > 1 for ids in trade_by_order.values())
                                       if verified_orders else None),
            "closed_orders": len(closed_trades),
            "refunded_orders": len({r["order_no"] for r in rows if r["action"] == "refund" and r["state"] == "REFUNDED"}),
            "trade_numbers": {order: sorted(numbers) for order, numbers in trade_by_order.items()},
            "closed_trade_numbers": closed_trades}


def sandbox_log(payment: dict) -> str:
    lines = ["# 支付宝沙箱联调记录", "",
             "这里汇总本机通过沙箱接口取得的交易状态。", ""]
    if not payment["verified"]:
        lines.append("付款后丢响应的恢复验收待完成。")
    else:
        lines.append(f"付款后丢响应并恢复查单已验证，同一订单对应多个交易号的订单数为 "
                     f"{payment['duplicate_trade_orders']}。")
    lines += [f"已确认关闭 {payment['closed_orders']} 单，已确认退款 {payment['refunded_orders']} 单。", ""]
    if payment["trade_numbers"] or payment["closed_trade_numbers"]:
        lines += ["| 场景 | 商户订单号 | 已核对的沙箱交易号 |", "| --- | --- | --- |"]
        for order, numbers in sorted(payment["trade_numbers"].items()):
            lines.append(f"| 付款与恢复 | `{order}` | " + "、".join(f"`{number}`" for number in numbers) + " |")
        for order, number in sorted(payment["closed_trade_numbers"].items()):
            lines.append(f"| 待付款关单 | `{order}` | `{number}` |" if number else f"| 待付款关单 | `{order}` | — |")
    return "\n".join(lines).rstrip() + "\n"


def write_report(report: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(format_report(report), encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out.parent / "sandbox_log.md").write_text(sandbox_log(report["payment"]), encoding="utf-8")


def format_report(report: dict) -> str:
    cap = report.get("amap_request_cap")
    calls = (f"{report['network_requests']}/{cap}" if cap is not None else str(report["network_requests"]))
    budget = "（本轮程序上限）" if cap is not None else ""
    lines = ["# WXG 真实接口评测", "",
             f"- 采样时间 {report['captured_at']}。高德调用 {calls} 次{budget}，"
             f"缓存命中 {report['cache_hits']} 次。账户剩余额度以高德控制台为准。",
             f"- {report['captured']}/{report['expected']} 组城市和日期取得预报。"
             f"{len(report['capture_errors'])} 项接口缺失单列。",
             "- 以未注入的高德响应作为干净对照。实验在同一批真实响应上回放注入，"
             "结果反映网关处置表现。", "",
             "| 配置 | 样本 | 用户受损 | 正常响应误报 | 失败结局 | 回放决策 P50/P95 | 模型失败 | 模型费用估算 |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for variant, item in report["variants"].items():
        clean = f"{item['false_alarms']}/{item['clean_samples']}" if item["clean_samples"] else "无样本"
        lines.append(f"| {variant} | {item['samples']} | {item['harm']}/{item['samples']} | {clean} | "
                     f"{item['failed']} | {item['decision_p50_ms']:.1f}/{item['decision_p95_ms']:.1f} ms | "
                     f"{item['model_failures']} | ¥{item['cost_cny']:.4f} |")
    net = report["network_fetch"]
    if net["n"]:
        lines += ["", f"实际发生网络访问的采样 P50/P95 为 {net['p50_ms']:.0f}/{net['p95_ms']:.0f} ms"
                  f"（{net['n']} 组，包含需要的地理编码调用）。"]
    lines += ["", "## 支付宝沙箱", ""]
    pay = report["payment"]
    if pay["verified"]:
        lines.append(f"已找到付款后丢响应、重复查单的联调记录。"
                     f"记录中已付款订单 {pay['orders']} 个，同一订单对应多个交易号 {pay['duplicate_trade_orders']} 个。"
                     f"已确认关闭 {pay['closed_orders']} 单，已确认退款 {pay['refunded_orders']} 单。"
                     " [联调记录](sandbox_log.md)")
    else:
        lines.append("待沙箱买家完成付款和恢复演示，真实重复交易次数待核验。")
    if report["capture_errors"]:
        lines += ["", "## 缺失响应", ""]
        lines.extend(f"- {item['city']} {item['date']}，{item['reason']}" for item in report["capture_errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--payment-only", action="store_true", help="使用本地沙箱日志更新现有评测")
    parser.add_argument("--model", default="deepseek-ai/DeepSeek-V3.2")
    parser.add_argument("--seeds", default="42,7,2026")
    parser.add_argument("--max-amap-requests", default=120, type=int)
    parser.add_argument("--fresh", action="store_true", help="使用独立缓存测量当天网络采样时延")
    parser.add_argument("--out", type=Path, default=ROOT / "eval/results_real.md")
    args = parser.parse_args()
    payment = payment_status(ROOT / "cache/alipay/events.jsonl")
    if args.payment_only:
        report = json.loads(args.out.with_suffix(".json").read_text(encoding="utf-8"))
        write_report({**report, "payment": payment}, args.out)
        return 0
    key = load_setting("AMAP_KEY")
    if not key:
        parser.exit(2, "缺少 AMAP_KEY，无法采集真实高德预报。\n")
    now = datetime.now(TZ).replace(microsecond=0)
    judge = None if args.no_llm else LLMJudge(args.model, prompt_version="v2", now=now)
    if judge and not judge.available:
        parser.exit(2, "缺少 SILICONFLOW_API_KEY。仅跑规则可加 --no-llm。\n")
    cases = json.loads((ROOT / "data/testset_real.json").read_text(encoding="utf-8"))["weather"]
    seeds = [int(seed) for seed in args.seeds.split(",")]
    cache_dir = ROOT / "cache/amap"
    if args.fresh:
        cache_dir = cache_dir / now.strftime("fresh-%Y%m%d-%H%M%S")
    client = AmapClient(key, cache_dir, max_requests=args.max_amap_requests, timeout=8.0)
    snapshots, errors = capture(client, cases, now)
    if not snapshots:
        parser.exit(2, "高德未返回可用天气预报，请检查控制台权限。\n")
    snapshot_path = cache_dir / "eval_capture.jsonl"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text("".join(json.dumps({"captured_at": now.isoformat(), "city": city, "date": date, **row},
                                               ensure_ascii=False) + "\n" for (city, date), row in snapshots.items()),
                             encoding="utf-8")
    rows = evaluate(cases, seeds, snapshots, now, judge)
    variants = sorted({row["variant"] for row in rows})
    network = [item["capture_ms"] for item in snapshots.values() if item["network_requests"]]
    report = {"captured_at": now.isoformat(), "seeds": seeds, "captured": len(snapshots),
              "expected": len(snapshots) + len(errors), "network_requests": client.request_count,
              "amap_request_cap": args.max_amap_requests, "cache_hits": client.cache_hits, "network_fetch": {"n": len(network), "p50_ms": pct(network, 50),
                                                                 "p95_ms": pct(network, 95)},
              "variants": {variant: summarize([row for row in rows if row["variant"] == variant])
                           for variant in variants},
              "capture_errors": [{"city": city, "date": date, "reason": reason}
                                 for (city, date), reason in errors.items()],
              "payment": payment}
    write_report(report, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
