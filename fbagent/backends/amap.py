"""Amap Web Service forecast and geocoding with a bounded request budget."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import math
from pathlib import Path
from time import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from ..world import TZ
from .base import ProviderFailure

BASE = "https://restapi.amap.com/v3"
FORECAST_TTL = 900
GEOCODE_TTL = 2_592_000
RATE_LIMIT_CODES = {"10003", "10004", "10010", "10019", "10020", "10021", "10044"}
CONFIG_CODES = {"10001", "10002", "10005", "10006", "10007", "10009", "10012", "10013", "10014"}


@dataclass
class AmapClient:
    key: str
    cache: Path
    max_requests: int = 120
    timeout: float = 4.0
    request_count: int = 0
    cache_hits: int = 0

    def _request(self, endpoint: str, params: dict, ttl: int) -> dict:
        cache_id = sha256(json.dumps([endpoint, params], sort_keys=True).encode()).hexdigest()
        target = self.cache / f"{cache_id}.json"
        try:
            if time() - target.stat().st_mtime <= ttl:
                cached = json.loads(target.read_text(encoding="utf-8"))
                if isinstance(cached, dict) and cached.get("status") == "1":
                    self.cache_hits += 1
                    return cached
        except (OSError, ValueError):
            pass
        if self.request_count >= self.max_requests:
            raise ProviderFailure(429, "高德调用已达本次运行上限")
        self.request_count += 1
        query = urlencode({**params, "key": self.key})
        try:
            with urlopen(f"{BASE}/{endpoint}?{query}", timeout=self.timeout) as response:
                body = json.load(response)
        except HTTPError as exc:
            raise ProviderFailure(exc.code, "高德接口返回 HTTP 错误") from None
        except (URLError, TimeoutError):
            raise ProviderFailure(0, "高德接口连接失败或超时") from None
        except (ValueError, UnicodeError):
            raise ProviderFailure(502, "高德接口返回无法解析") from None
        if not isinstance(body, dict):
            raise ProviderFailure(502, "高德接口返回格式异常")
        if body.get("status") != "1":
            code = body.get("infocode")
            if code in RATE_LIMIT_CODES:
                raise ProviderFailure(429, "高德服务调用受限")
            if code in CONFIG_CODES:
                raise ProviderFailure(403, "高德 Key 或 Web 服务权限配置有误")
            raise ProviderFailure(502, "高德接口返回业务错误")
        self.cache.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        return body

    def geocode(self, city: str) -> dict:
        data = self._request("geocode/geo", {"address": city, "city": city}, GEOCODE_TTL)
        for item in data.get("geocodes", ()):
            if not isinstance(item, dict):
                continue
            for name in (item.get("city"), item.get("district"), item.get("province")):
                if isinstance(name, str) and _city_name(name) == _city_name(city):
                    code = item.get("adcode")
                    if isinstance(code, str) and code.isascii() and code.isdigit() and len(code) == 6:
                        return item
        raise ProviderFailure(404, "高德地理编码未返回匹配城市")

    def forecast(self, city: str, date: str) -> dict:
        adcode = self.geocode(city)["adcode"]
        data = self._request("weather/weatherInfo", {"city": adcode, "extensions": "all"}, FORECAST_TTL)
        forecasts = data.get("forecasts") or []
        if not forecasts:
            raise ProviderFailure(404, "高德没有返回该城市的天气预报")
        forecast = forecasts[0]
        try:
            cast = next((item for item in forecast["casts"] if item["date"] == date), None)
            if cast is None:
                raise ProviderFailure(404, "请求日期超出高德返回的预报范围")
            day = float(cast["daytemp"])
            night = float(cast["nighttemp"])
            if not all(math.isfinite(temp) for temp in (day, night)):
                raise ValueError("non-finite forecast")
            stamp = datetime.strptime(forecast["reporttime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
            upstream_city = _city_name(forecast["city"])
            result_city = city if upstream_city == _city_name(city) else upstream_city
            if str(forecast["adcode"]) != adcode and result_city == city:
                result_city = f"{result_city}（区域编码 {forecast['adcode']}）"
            day_weather = cast["dayweather"]
            night_weather = cast["nightweather"]
            if not isinstance(day_weather, str) or not isinstance(night_weather, str):
                raise TypeError("weather label")
            return {"city": result_city, "date": cast["date"], "condition": day_weather,
                    "night_condition": night_weather, "temp_high_c": max(day, night),
                    "temp_low_c": min(day, night), "updated_at": stamp.isoformat(),
                    "source": "高德天气预报", "adcode": str(forecast["adcode"])}
        except (KeyError, TypeError, ValueError):
            raise ProviderFailure(502, "高德预报缺少可用的日期、天气或发布时间") from None


def _city_name(value: str) -> str:
    return value.removesuffix("市").strip()
