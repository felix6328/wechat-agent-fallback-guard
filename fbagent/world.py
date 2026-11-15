"""模拟世界的「真值」。健康服务按真值返回；注入故障时在真值上做扰动。

全部为合成数据（synthetic），不是真实天气、真实商户或真实价格。
模拟当前时刻固定为 2026-11-15 12:00（Asia/Shanghai），保证可复现。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=TZ)

DATES = {"今天": "2026-11-15", "明天": "2026-11-16", "后天": "2026-11-17"}

# (city, date) -> 天气真值
WEATHER = {
    "北京": {"condition": "晴", "temp_high_c": 9, "temp_low_c": -1, "precip_mm": 0.0},
    "上海": {"condition": "小雨", "temp_high_c": 16, "temp_low_c": 11, "precip_mm": 6.5},
    "广州": {"condition": "多云", "temp_high_c": 30, "temp_low_c": 22, "precip_mm": 0.0},
    "深圳": {"condition": "晴", "temp_high_c": 27, "temp_low_c": 20, "precip_mm": 0.0},
    "漠河": {"condition": "小雪", "temp_high_c": -18, "temp_low_c": -32, "precip_mm": 1.2},
    "杭州": {"condition": "阴", "temp_high_c": 15, "temp_low_c": 9, "precip_mm": 0.0},
    "成都": {"condition": "阴", "temp_high_c": 14, "temp_low_c": 10, "precip_mm": 0.3},
    "哈尔滨": {"condition": "多云", "temp_high_c": -3, "temp_low_c": -14, "precip_mm": 0.0},
}

RESTAURANTS = {
    "老王黄焖鸡": {
        "items": [
            {"name": "黄焖鸡米饭", "price_cny": 25.8},
            {"name": "黄焖排骨饭", "price_cny": 29.8},
            {"name": "免费加饭", "price_cny": 0.0, "note": "每单限一份赠品"},
            {"name": "可乐", "price_cny": 4.0},
        ],
        "distance_km": 2.1, "delivery_eta_min": 32, "note": "",
    },
    "杨国福麻辣烫": {
        "items": [
            {"name": "麻辣烫（按份）", "price_cny": 32.0},
            {"name": "炸串拼盘", "price_cny": 18.0},
            {"name": "酸梅汤", "price_cny": 6.0},
        ],
        "distance_km": 1.5, "delivery_eta_min": 28, "note": "",
    },
    "沙县小吃": {
        "items": [
            {"name": "拌面", "price_cny": 8.0},
            {"name": "蒸饺", "price_cny": 9.0},
            {"name": "鸡腿饭", "price_cny": 16.0},
            {"name": "扁肉", "price_cny": 7.0},
        ],
        "distance_km": 0.8, "delivery_eta_min": 22, "note": "",
    },
    "一点点": {
        "items": [
            {"name": "波霸奶茶", "price_cny": 13.0},
            {"name": "芝芝莓莓", "price_cny": 23.8},
            {"name": "柠檬绿茶", "price_cny": 11.0},
        ],
        "distance_km": 1.2, "delivery_eta_min": 25, "note": "",
    },
    "川味小馆": {
        "items": [
            {"name": "水煮鱼", "price_cny": 58.0},
            {"name": "回锅肉", "price_cny": 36.0},
            {"name": "米饭", "price_cny": 2.0},
        ],
        "distance_km": 6.8, "delivery_eta_min": 95, "note": "雨天高峰，骑手紧张，配送较慢",
    },
}

# 地点之间的真值距离与时长
ROUTES = {
    ("家", "公司"): {"distance_km": 18.5, "drive_min": 40, "walk_min": 230},
    ("公司", "浦东机场"): {"distance_km": 62.0, "drive_min": 70, "walk_min": 760},
    ("家", "地铁站"): {"distance_km": 0.2, "drive_min": 2, "walk_min": 3},
    ("家", "虹桥火车站"): {"distance_km": 24.0, "drive_min": 45, "walk_min": 300},
    ("公司", "家"): {"distance_km": 18.5, "drive_min": 40, "walk_min": 230},
}


def route(origin: str, dest: str) -> dict:
    r = ROUTES.get((origin, dest)) or ROUTES.get((dest, origin))
    if r is None:
        raise KeyError(f"unknown route {origin}->{dest}")
    return r


def ride_fare(distance_km: float, drive_min: float) -> float:
    # 合成计价：起步 13 + 2.8/公里 + 0.5/分钟
    return round(13 + 2.8 * distance_km + 0.5 * drive_min, 1)


def ts(dt: datetime) -> str:
    return dt.isoformat(timespec="minutes")
