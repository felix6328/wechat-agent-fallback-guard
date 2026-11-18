"""Deterministic query-first recovery for manual sandbox payments."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Protocol

from .backends.alipay import Trade
from .backends.base import ProviderFailure


PAID_RESPONSE_DROPPED = "fault: 已付款的查询响应丢失"


class SandboxPayment(Protocol):
    def query(self, order_no: str) -> Trade: ...
    def create(self, order_no: str, amount: Decimal, method: str) -> Trade: ...


def order_number(session_id: str, order_id: str) -> str:
    payload = json.dumps([session_id, order_id], separators=(",", ":"), ensure_ascii=False)
    return "wxg" + sha256(payload.encode()).hexdigest()[:36]


def reserve_order(path: Path, order_no: str, amount: Decimal, method: str) -> None:
    """Persist the order's intent across retries before a hosted checkout opens."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("""CREATE TABLE IF NOT EXISTS payment_intent (
            order_no TEXT PRIMARY KEY, amount TEXT NOT NULL, method TEXT NOT NULL
        )""")
        values = (order_no, str(amount), method)
        db.execute("INSERT OR IGNORE INTO payment_intent VALUES (?, ?, ?)", values)
        saved = db.execute("SELECT amount, method FROM payment_intent WHERE order_no = ?",
                           (order_no,)).fetchone()
        if saved != (str(amount), method):
            raise ValueError("同一沙箱订单已对应另一组金额或收银台方式，请核对原订单")


@dataclass
class Recovery:
    service: SandboxPayment
    order_no: str
    amount: Decimal
    trace: list[str] = field(default_factory=list)
    dropped_trade_no: str = ""

    @property
    def dropped_paid_response(self) -> bool:
        return bool(self.dropped_trade_no)

    def _query(self, *, drop_paid_response: bool = False) -> Trade:
        self.trace.append("trade.query")
        trade = self.service.query(self.order_no)
        if trade.order_no != self.order_no:
            return Trade("MISMATCH", self.order_no)
        if trade.state in {"PENDING", "PAID", "CLOSED"} and self.amount != trade.amount:
            return Trade("MISMATCH", self.order_no)
        if trade.state == "PAID":
            if not trade.trade_no or (self.dropped_trade_no and self.dropped_trade_no != trade.trade_no):
                return Trade("MISMATCH", self.order_no)
            if drop_paid_response and not self.dropped_trade_no:
                self.dropped_trade_no = trade.trade_no
                self.trace.append(PAID_RESPONSE_DROPPED)
                raise ProviderFailure(0, "local fault")
        return trade

    def start(self, method: str = "page") -> Trade:
        try:
            existing = self._query()
        except ProviderFailure:
            return Trade("UNKNOWN", self.order_no)
        if existing.state != "NOT_FOUND":
            return existing
        self.trace.append("trade.page.pay" if method == "page" else "trade.precreate")
        try:
            created = self.service.create(self.order_no, self.amount, method)
        except ProviderFailure:
            return self.confirm()
        if created.order_no != self.order_no or created.amount != self.amount or created.state != "PENDING":
            return Trade("MISMATCH", self.order_no)
        return created

    def confirm(self, *, drop_paid_response: bool = False) -> Trade:
        try:
            trade = self._query(drop_paid_response=drop_paid_response)
        except ProviderFailure:
            try:
                return self._query()
            except ProviderFailure:
                return Trade("UNKNOWN", self.order_no)
        return trade
