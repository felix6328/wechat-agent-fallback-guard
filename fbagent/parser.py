"""指令解析：确定性的关键词 + 词表路由。

本项目评测的是「工具返回质检与兜底」，不是意图理解，所以解析器刻意做成确定性的，
避免把 NLU 误差混进兜底指标。解析准确率在评测里单独报告（测试集是按词表写的，存在循环，不外推）。
"""
from __future__ import annotations

import re

from . import world as W

PLACES = ["浦东机场", "虹桥火车站", "地铁站", "公司", "家"]
CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "十": 10, "二十": 20}


def _dishes():
    out = {}
    for r, info in W.RESTAURANTS.items():
        for it in info["items"]:
            out[it["name"]] = r
    return out


def _qty_before(text: str, dish: str) -> int:
    m = re.search(r"(\d+|二十|[一两二三四五六十])\s*(份|杯|碗|个)\s*" + re.escape(dish), text)
    if not m:
        return 1
    g = m.group(1)
    return int(g) if g.isdigit() else CN_NUM[g]


def _places(text: str):
    found = sorted([(text.find(p), p) for p in PLACES if p in text])
    # 「从X到Y」「X去Y」：按出现顺序，第一个为起点
    return [p for _, p in found]


def parse(text: str) -> dict:
    city = next((c for c in W.WEATHER if c in text), None)
    date = next((W.DATES[k] for k in W.DATES if k in text), W.DATES["今天"])
    rest = next((r for r in W.RESTAURANTS if r in text), None)
    dishes = _dishes()
    # 菜名按长度降序匹配，避免「米饭」吃掉「黄焖鸡米饭」
    matched = []
    tmp = text.replace(rest, "#") if rest else text
    for d in sorted(dishes, key=len, reverse=True):
        key = d.split("（")[0]
        if key in tmp:
            matched.append(d)
            tmp = tmp.replace(key, "#")
    places = _places(text)
    if city and ("叫车" in text or "打车" in text) and len(places) >= 2:
        return {"intent": "weather_ride", "city": city, "date": date, "origin": places[0], "dest": places[1]}
    if city and ("天气" in text or "温度" in text or "下雨" in text or "冷" in text or "穿" in text):
        return {"intent": "weather", "city": city, "date": date}
    if ("打车" in text or "叫车" in text or "叫个车" in text or "车费" in text) and len(places) >= 2:
        return {"intent": "ride", "origin": places[0], "dest": places[1]}
    if ("路线" in text or "多远" in text or "怎么走" in text or "步行" in text) and len(places) >= 2:
        return {"intent": "route", "origin": places[0], "dest": places[1], "mode": "walk" if "步行" in text or "走路" in text else "drive"}
    if matched and not rest:
        rest = dishes[matched[0]]
    if rest and ("点" in text or "下单" in text or "买" in text or "来" in text) and matched:
        items = [{"name": d, "qty": _qty_before(text, d.split("（")[0])} for d in matched]
        return {"intent": "food_order", "restaurant": rest, "items": items,
                "pay": any(k in text for k in ("付款", "支付", "付了", "结账"))}
    if rest:
        return {"intent": "food_menu", "restaurant": rest, "dish": matched[0].split("（")[0] if matched else None}
    return {"intent": "unknown"}
