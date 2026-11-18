from datetime import datetime
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fbagent.backends.alipay import AlipaySandbox, Trade, parse_amount
from fbagent.backends.amap import AmapClient
from fbagent.backends.base import ProviderFailure
from fbagent.backends.real import RealEnv
from fbagent.envload import load_setting
from fbagent.evaluate import run_case
from fbagent.payment import PAID_RESPONSE_DROPPED, Recovery, order_number, reserve_order
from fbagent.world import TZ

NOW = datetime(2026, 11, 17, 12, 30, tzinfo=TZ)
GATEWAY = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"
AMOUNT = Decimal("0.01")


class FakeAmap:
    def forecast(self, city, day):
        return {"source": "高德天气预报", "city": city, "date": day, "condition": "晴",
                "updated_at": "2026-11-17T12:00:00+08:00", "temp_low_c": 19, "temp_high_c": 26}


class FakeSandbox:
    def __init__(self, order, responses):
        self.order = order
        self.responses = iter(responses)
        self.creations = []

    def query(self, order_no):
        if order_no != self.order:
            raise AssertionError("unexpected order number")
        result = next(self.responses)
        if isinstance(result, ProviderFailure):
            raise result
        return result

    def create(self, order_no, amount, method):
        self.creations.append((order_no, amount, method))
        return Trade("PENDING", order_no, amount=amount, checkout="sandbox-url")


class WeatherTests(unittest.TestCase):
    def test_real_date_and_report_time_are_used(self):
        case = {"id": "live", "instruction": "广州明天天气"}
        result = run_case(case, "rules_strict", env=RealEnv("live", amap=FakeAmap(), observed_at=NOW))
        self.assertEqual(result["plan"]["date"], "2026-11-18")
        self.assertEqual(result["outcome"], "ok")
        self.assertIn("高德天气预报", result["reply"])

    def test_city_fault_is_not_hidden_by_normalization_and_no_mock_backup(self):
        case = {"id": "live-fault", "instruction": "广州明天天气"}
        env = RealEnv(case["id"], {"weather.query": ["sem_city"]}, amap=FakeAmap(), observed_at=NOW)
        result = run_case(case, "rules_strict", env=env)
        self.assertEqual(result["calls"][0]["pred_type"], "context_mismatch")
        self.assertEqual(len(result["calls"]), 1)
        self.assertIn("暂时不可靠", result["reply"])
        self.assertFalse(result["exposure"])

    def test_amap_normalizes_signed_temperature_and_city(self):
        geo = {"geocodes": [{"city": "广州市", "adcode": "440100"}]}
        weather = {"forecasts": [{"city": "广州市", "adcode": "440100", "reporttime": "2026-11-17 12:00:00",
                                  "casts": [{"date": "2026-11-17", "daytemp": "-6", "nighttemp": "-2",
                                             "dayweather": "雪", "nightweather": "阴"}]}]}
        with tempfile.TemporaryDirectory() as tmp:
            client = AmapClient("fake", Path(tmp))
            with patch.object(client, "_request", side_effect=[geo, weather]):
                data = client.forecast("广州", "2026-11-17")
        self.assertEqual((data["city"], data["temp_low_c"], data["temp_high_c"]), ("广州", -6, -2))
        self.assertEqual(data["updated_at"], "2026-11-17T12:00:00+08:00")

    def test_shared_env_ignores_unrelated_variables(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shared.env"
            path.write_text("\n".join(("JWT_SIGNING_SECRET=dummy", "export AMAP_KEY='fake'", "")))
            with patch.dict("os.environ", {"FB_ENV_FILE": str(path)}):
                self.assertEqual(load_setting("AMAP_KEY"), "fake")
                with self.assertRaises(ValueError):
                    load_setting("JWT_SIGNING_SECRET")


class PaymentTests(unittest.TestCase):
    def setUp(self):
        self.order = order_number("local-session", "local-order")

    def test_paid_response_drop_requeries_without_create(self):
        paid = Trade("PAID", self.order, "txn-local", AMOUNT)
        service = FakeSandbox(self.order, [paid, paid])
        recovery = Recovery(service, self.order, AMOUNT)
        self.assertEqual(recovery.confirm(drop_paid_response=True), paid)
        self.assertTrue(recovery.dropped_paid_response)
        self.assertEqual(recovery.trace.count("trade.query"), 2)
        self.assertEqual(service.creations, [])

    def test_checkouts_require_confirmed_absence_and_same_trade_id(self):
        service = FakeSandbox(self.order, [Trade("NOT_FOUND", self.order)])
        recovery = Recovery(service, self.order, AMOUNT)
        self.assertEqual(recovery.start().state, "PENDING")
        self.assertEqual(service.creations, [(self.order, AMOUNT, "page")])
        self.assertEqual(recovery.trace, ["trade.query", "trade.page.pay"])

    def test_pending_and_timeout_never_create_a_second_checkout(self):
        for first in (Trade("PENDING", self.order, amount=AMOUNT), ProviderFailure(0, "timeout")):
            service = FakeSandbox(self.order, [first])
            Recovery(service, self.order, AMOUNT).start()
            self.assertEqual(service.creations, [])

    def test_amount_mismatch_blocks_and_production_gateway_is_rejected(self):
        service = FakeSandbox(self.order, [Trade("PAID", self.order, "txn-local", Decimal("2.00"))])
        self.assertEqual(Recovery(service, self.order, AMOUNT).confirm().state, "MISMATCH")
        with self.assertRaises(ValueError):
            AlipaySandbox(object(), "https://openapi.alipay.com/gateway.do")
        with self.assertRaises(ValueError):
            parse_amount("1.001")


    def test_order_amount_and_checkout_method_are_stable_across_restarts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "orders.sqlite"
            reserve_order(path, self.order, AMOUNT, "page")
            reserve_order(path, self.order, AMOUNT, "page")
            with self.assertRaises(ValueError):
                reserve_order(path, self.order, Decimal("2.00"), "page")
            with self.assertRaises(ValueError):
                reserve_order(path, self.order, AMOUNT, "qr")


    def test_poll_injects_lost_response_once_and_pins_the_observed_trade_number(self):
        paid = Trade("PAID", self.order, "txn-local", AMOUNT)
        pending = Trade("PENDING", self.order, amount=AMOUNT)
        changed = Trade("PAID", self.order, "txn-different", AMOUNT)
        service = FakeSandbox(self.order, [paid, pending, paid, changed])
        recovery = Recovery(service, self.order, AMOUNT)
        self.assertEqual(recovery.confirm(drop_paid_response=True).state, "PENDING")
        self.assertEqual(recovery.confirm(drop_paid_response=True), paid)
        self.assertEqual(recovery.confirm(drop_paid_response=True).state, "MISMATCH")
        self.assertEqual(recovery.trace.count(PAID_RESPONSE_DROPPED), 1)
        self.assertEqual(service.creations, [])
