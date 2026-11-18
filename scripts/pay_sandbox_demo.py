"""Create and reconcile one sandbox trade. No buyer credentials are collected."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from time import monotonic, sleep

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fbagent.backends.alipay import AlipaySandbox, Trade, parse_amount  # noqa: E402
from fbagent.backends.base import ProviderFailure  # noqa: E402
from fbagent.payment import Recovery, order_number, reserve_order  # noqa: E402
from fbagent.world import TZ  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="支付宝沙箱的下单、付款后查单和恢复演示")
    parser.add_argument("action", choices=("start", "verify", "close", "refund"))
    parser.add_argument("--session", required=True, help="本轮固定会话 ID")
    parser.add_argument("--order", default="demo", help="本轮固定业务订单 ID")
    parser.add_argument("--amount", default="0.01")
    parser.add_argument("--method", choices=("page", "qr"), default="page")
    parser.add_argument("--drop-paid-response", action="store_true")
    parser.add_argument("--wait-seconds", default=0, type=int, help="verify 轮询待支付订单的最长时长")
    args = parser.parse_args()
    if (args.drop_paid_response or args.wait_seconds) and args.action != "verify":
        parser.error("--drop-paid-response 和 --wait-seconds 用于 verify")
    if not 0 <= args.wait_seconds <= 300:
        parser.error("--wait-seconds 应在 0 到 300 之间")
    try:
        service = AlipaySandbox.from_settings()
        amount = parse_amount(args.amount)
        order_no = order_number(args.session, args.order)
        recovery = Recovery(service, order_no, amount)
        if args.action == "start":
            reserve_order(ROOT / "cache/alipay/orders.sqlite", order_no, amount, args.method)
            trade = recovery.start(args.method)
        else:
            deadline = monotonic() + args.wait_seconds
            trade = recovery.confirm(drop_paid_response=args.drop_paid_response)
            while trade.state in {"PENDING", "NOT_FOUND", "UNKNOWN"} and monotonic() < deadline:
                sleep(max(0, min(3, deadline - monotonic())))
                trade = recovery.confirm(drop_paid_response=args.drop_paid_response)
            if args.action == "close":
                if trade.state == "NOT_FOUND":
                    raise ValueError("沙箱暂未查到交易。请先打开该测试单的收银台，停留在待付款页面后重试。")
                if trade.state != "PENDING":
                    raise ValueError(f"关单需要待支付且金额匹配的交易，当前查询状态为 {trade.state}")
                service.close(order_no)
                recovery.trace.append("trade.close")
                trade = recovery.confirm()
            elif args.action == "refund":
                if trade.state != "PAID" or not trade.trade_no:
                    raise ValueError("只有已支付且金额匹配的订单可退款")
                recovery.trace.append("trade.refund")
                try:
                    service.refund(order_no, amount)
                except ProviderFailure:
                    pass  # The write may have succeeded even if the caller did not receive a reply.
                recovery.trace.append("trade.fastpay.refund.query")
                confirmed = service.refund_confirmed(order_no, amount)
                trade = Trade("REFUNDED" if confirmed else "REFUND_PENDING", order_no,
                              trade.trade_no, amount)
    except (ValueError, ProviderFailure) as exc:
        print(exc, file=sys.stderr)
        return 2
    print(f"沙箱订单 {trade.order_no} · {trade.state}")
    print(" → ".join(recovery.trace))
    if trade.checkout:
        print(f"沙箱付款入口：{trade.checkout}")
    if trade.trade_no:
        print(f"沙箱交易号：{trade.trade_no}")
    log_path = ROOT / "cache/alipay/events.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as stream:
        record = {"time": datetime.now(TZ).isoformat(), "action": args.action, "order_no": trade.order_no,
                  "trade_no": trade.trade_no, "state": trade.state, "trace": recovery.trace,
                  "dropped_paid_response": recovery.dropped_paid_response, "amount": str(amount)}
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    if args.drop_paid_response and not (recovery.dropped_paid_response and trade.state == "PAID"):
        print("还未验证到已付款响应丢失后的恢复。先在沙箱收银台付款，再用同一会话和订单查单。")
        return 1
    if args.action == "close":
        return int(trade.state != "CLOSED")
    if args.action == "refund":
        return int(trade.state != "REFUNDED")
    return int(trade.state in {"UNKNOWN", "MISMATCH"})


if __name__ == "__main__":
    raise SystemExit(main())
