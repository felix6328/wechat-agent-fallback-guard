"""Live checks are opt-in. This suite never creates or pays for a trade."""
from datetime import datetime
import os
from pathlib import Path
import tempfile
import unittest

from fbagent.backends.alipay import AlipaySandbox
from fbagent.backends.amap import AmapClient
from fbagent.backends.base import ProviderFailure
from fbagent.envload import load_setting
from fbagent.payment import order_number
from fbagent.world import TZ


@unittest.skipUnless(os.getenv("FB_RUN_NETWORK") == "1", "未启用联网联调")
class ProviderIntegration(unittest.TestCase):
    def test_amap_live_forecast(self):
        key = load_setting("AMAP_KEY")
        if not key:
            self.skipTest("未配置高德 Web 服务 Key")
        with tempfile.TemporaryDirectory() as temp:
            client = AmapClient(key, Path(temp), timeout=8.0)
            data = client.forecast("广州", datetime.now(TZ).date().isoformat())
        self.assertEqual(data["city"], "广州")
        self.assertEqual(data["source"], "高德天气预报")
        self.assertIsNotNone(datetime.fromisoformat(data["updated_at"]).tzinfo)

    def test_alipay_signed_read_only_query(self):
        fields = ("ALIPAY_APP_ID", "ALIPAY_GATEWAY", "ALIPAY_PUBLIC_KEY")
        if not all(load_setting(field) for field in fields) or not any(
            load_setting(field) for field in ("ALIPAY_APP_PRIVATE_KEY_FILE", "ALIPAY_APP_PRIVATE_KEY")
        ):
            self.skipTest("支付宝沙箱配置尚未填齐")
        sandbox = AlipaySandbox.from_settings()
        try:
            result = sandbox.query(order_number("wxg-integration", "readonly-absent-order"))
        except ProviderFailure as exc:
            if exc.status == 0:
                self.skipTest("支付宝沙箱暂时无法返回已验签响应，需核对网关或维护状态")
            raise
        self.assertEqual(result.state, "NOT_FOUND")
