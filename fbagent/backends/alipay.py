"""Official Alipay SDK adapter for sandbox checkout and signed trade queries."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from importlib import import_module
import base64
import json
from pathlib import Path
from urllib.parse import urlsplit

from ..envload import load_setting
from .base import ProviderFailure

SANDBOX_GATEWAYS = frozenset({
    "https://openapi-sandbox.dl.alipaydev.com/gateway.do",
    "https://openapi.alipaydev.com/gateway.do",
})
API = "alipay.aop.api."


@dataclass(frozen=True)
class Trade:
    state: str
    order_no: str
    trade_no: str = ""
    amount: Decimal | None = None
    checkout: str = ""


class AlipaySandbox:
    def __init__(self, client, gateway: str):
        if gateway not in SANDBOX_GATEWAYS:
            raise ValueError("支付宝网关必须是官方沙箱地址")
        self.client, self.gateway = client, gateway

    @classmethod
    def from_settings(cls) -> AlipaySandbox:
        gateway = load_setting("ALIPAY_GATEWAY")
        app_id = load_setting("ALIPAY_APP_ID")
        public = load_setting("ALIPAY_PUBLIC_KEY")
        private_file = load_setting("ALIPAY_APP_PRIVATE_KEY_FILE")
        private = load_setting("ALIPAY_APP_PRIVATE_KEY")
        if not all((gateway, app_id, public, private_file or private)):
            raise ValueError("支付宝沙箱配置不全，请检查 APPID、网关、应用私钥文件和支付宝公钥")
        if gateway not in SANDBOX_GATEWAYS:
            raise ValueError("支付宝网关必须是官方沙箱地址")
        try:
            from Crypto.PublicKey import RSA
            from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
            from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
        except ImportError:
            raise ValueError("请先安装 requirements-real.txt") from None
        try:
            if private_file:
                private = Path(private_file).expanduser().read_text(encoding="utf-8")
            rsa_private_key = RSA.import_key(_key_bytes(private))
            rsa_public_key = RSA.import_key(_key_bytes(public))
            if not rsa_private_key.has_private() or rsa_public_key.has_private():
                raise ValueError("wrong type")
        except (OSError, TypeError, ValueError):
            raise ValueError("无法读取支付宝沙箱密钥，请检查文件路径和 RSA2 密钥类型") from None
        config = AlipayClientConfig()
        config.app_id, config.server_url = app_id, gateway
        config.app_private_key = rsa_private_key.export_key(format="PEM", pkcs=1).decode("ascii")
        config.alipay_public_key = rsa_public_key.export_key(format="PEM").decode("ascii")
        config.sign_type = "RSA2"
        config.timeout = 8
        return cls(DefaultAlipayClient(alipay_client_config=config), gateway)

    def _request(self, name: str, params: dict, *, page: bool = False):
        request_class = f"AlipayTrade{name}Request"
        module = import_module(f"{API}request.{request_class}")
        request = getattr(module, request_class)()
        request.biz_content = params
        try:
            if page:
                return self.client.page_execute(request, http_method="GET")
            result = json.loads(self.client.execute(request))
        except Exception:
            raise ProviderFailure(0, "支付宝沙箱请求或验签未完成，支付状态待确认") from None
        if not isinstance(result, dict):
            raise ProviderFailure(502, "支付宝沙箱返回格式异常")
        return result

    def query(self, order_no: str) -> Trade:
        body = self._request("Query", {"out_trade_no": order_no})
        if body.get("sub_code") == "ACQ.TRADE_NOT_EXIST":
            return Trade("NOT_FOUND", order_no)
        self._success(body, "查单")
        states = {"WAIT_BUYER_PAY": "PENDING", "TRADE_SUCCESS": "PAID",
                  "TRADE_FINISHED": "PAID", "TRADE_CLOSED": "CLOSED"}
        state = states.get(body.get("trade_status"), "UNKNOWN")
        trade_no = body.get("trade_no") or ""
        if body.get("out_trade_no") != order_no or not isinstance(trade_no, str):
            raise ProviderFailure(502, "支付宝沙箱查单的订单号不匹配")
        try:
            amount = parse_amount(body["total_amount"])
        except (KeyError, ValueError):
            raise ProviderFailure(502, "支付宝沙箱查单缺少可核对的金额") from None
        if state == "PAID" and not trade_no:
            raise ProviderFailure(502, "支付宝沙箱已支付状态缺少交易号")
        return Trade(state, order_no, trade_no, amount)

    def create(self, order_no: str, amount: Decimal, method: str) -> Trade:
        params = {"out_trade_no": order_no, "total_amount": str(amount), "subject": "WXG 网关联调测试单"}
        if method == "page":
            checkout = self._request("PagePay", {**params, "product_code": "FAST_INSTANT_TRADE_PAY"}, page=True)
            if not _checkout_url(checkout, self.gateway):
                raise ProviderFailure(502, "支付宝沙箱收银台地址异常")
        elif method == "qr":
            body = self._request("Precreate", params)
            self._success(body, "创建待支付单")
            checkout = body.get("qr_code")
            if body.get("out_trade_no") != order_no or not isinstance(checkout, str) or not checkout:
                raise ProviderFailure(502, "支付宝沙箱待支付单信息不匹配")
        else:
            raise ValueError("支付方式可选 page 或 qr")
        return Trade("PENDING", order_no, amount=amount, checkout=checkout)

    def close(self, order_no: str) -> None:
        self._success(self._request("Close", {"out_trade_no": order_no}), "关闭订单")

    def refund(self, order_no: str, amount: Decimal) -> None:
        body = self._request("Refund", {"out_trade_no": order_no, "refund_amount": str(amount),
                                        "out_request_no": "refund-" + order_no})
        self._success(body, "退款")

    def refund_confirmed(self, order_no: str, amount: Decimal) -> bool:
        refund_id = "refund-" + order_no
        body = self._request("FastpayRefundQuery", {"out_trade_no": order_no, "out_request_no": refund_id})
        self._success(body, "退款查询")
        try:
            return (body["refund_status"] == "REFUND_SUCCESS" and body["out_trade_no"] == order_no
                    and body["out_request_no"] == refund_id and parse_amount(body["refund_amount"]) == amount)
        except (KeyError, ValueError):
            return False

    @staticmethod
    def _success(result: dict, action: str) -> None:
        if result.get("code") != "10000":
            raise ProviderFailure(502, f"支付宝沙箱{action}未确认")


def parse_amount(value) -> Decimal:
    try:
        amount = Decimal(str(value))
        if amount.is_finite() and 0 < amount <= Decimal("999999.99") and amount == amount.quantize(Decimal("0.01")):
            return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        pass
    raise ValueError("金额必须大于零且最多两位小数")


def _key_bytes(value: str) -> bytes:
    value = value.replace("\\n", "\n").strip()
    return value.encode("ascii") if value.startswith("-----") else base64.b64decode("".join(value.split()), validate=True)


def _checkout_url(checkout: str, gateway: str) -> bool:
    if not isinstance(checkout, str):
        return False
    url = urlsplit(checkout)
    return checkout.startswith(gateway + "?") and bool(url.query)
