"""Verify the SDK contract offline with ephemeral keys and a signed fixture."""

import base64
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from fbagent.backends.alipay import AlipaySandbox
from fbagent.backends.base import ProviderFailure
from fbagent.payment import order_number

GATEWAY = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"


@unittest.skipUnless(importlib.util.find_spec("alipay") is not None, "未安装真实沙箱 SDK")
class SDKContract(unittest.TestCase):
    def test_signed_query_and_page_request(self):
        from Crypto.Hash import SHA256
        from Crypto.PublicKey import RSA
        from Crypto.Signature import pkcs1_15

        app_key, platform_key = RSA.generate(2048), RSA.generate(2048)
        order = order_number("sdk-test", "order")
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "synthetic.pem"
            der = app_key.export_key(format="DER", pkcs=8)
            file.write_text(base64.b64encode(der).decode("ascii"))
            settings = {"ALIPAY_GATEWAY": GATEWAY, "ALIPAY_APP_ID": "local-test",
                        "ALIPAY_APP_PRIVATE_KEY_FILE": str(file),
                        "ALIPAY_PUBLIC_KEY": platform_key.public_key().export_key().decode("ascii")}
            with patch("fbagent.backends.alipay.load_setting", side_effect=lambda field: settings.get(field, "")):
                sandbox = AlipaySandbox.from_settings()
            body = {"code": "10000", "out_trade_no": order, "trade_no": "sandbox-local-paid",
                    "trade_status": "TRADE_SUCCESS", "total_amount": "0.01"}
            encoded = json.dumps(body, separators=(",", ":")).encode()
            signature = base64.b64encode(pkcs1_15.new(platform_key).sign(SHA256.new(encoded)))
            packet = b'{"alipay_trade_query_response":' + encoded + b',"sign":"' + signature + b'"}'
            with patch("alipay.aop.api.DefaultAlipayClient.do_post", return_value=packet):
                trade = sandbox.query(order)
                self.assertEqual((trade.state, trade.amount), ("PAID", Decimal("0.01")))
            tampered = packet.replace(b'"0.01"', b'"0.02"')
            with patch("alipay.aop.api.DefaultAlipayClient.do_post", return_value=tampered):
                with self.assertRaises(ProviderFailure):
                    sandbox.query(order)
            pending = sandbox.create(order, Decimal("0.01"), "page")
            query = parse_qs(urlsplit(pending.checkout).query)
            self.assertEqual(query["sign_type"], ["RSA2"])
            self.assertEqual(query["method"], ["alipay.trade.page.pay"])
            self.assertEqual(json.loads(query["biz_content"][0])["out_trade_no"], order)
            self.assertEqual(pending.state, "PENDING")
