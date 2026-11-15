"""解析评测集 data/parse_set.json：主测试集 + 留出集里的全部指令（金标 = 已校验的计划），
外加 36 条口语化改写（金标手写），专门考词表解析覆盖不到的说法。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fbagent.parser import parse  # noqa: E402
from fbagent import world as W  # noqa: E402

D = W.DATES
P = [
    ("帮我瞅瞅魔都明儿个天气", {"intent": "weather", "city": "上海", "date": D["明天"]}),
    ("帝都今天冷不冷啊", {"intent": "weather", "city": "北京", "date": D["今天"]}),
    ("羊城后天会不会下雨", {"intent": "weather", "city": "广州", "date": D["后天"]}),
    ("冰城明天要穿羽绒服吗", {"intent": "weather", "city": "哈尔滨", "date": D["明天"]}),
    ("蓉城今儿个天儿咋样", {"intent": "weather", "city": "成都", "date": D["今天"]}),
    ("杭州明天出门要带伞不", {"intent": "weather", "city": "杭州", "date": D["明天"]}),
    ("深圳后天热吗", {"intent": "weather", "city": "深圳", "date": D["后天"]}),
    ("漠河那边现在多少度", {"intent": "weather", "city": "漠河", "date": D["今天"]}),
    ("明天魔都要下雨的话从家给我叫个车去单位", {"intent": "weather_ride", "city": "上海", "date": D["明天"], "origin": "家", "dest": "公司"}),
    ("后天杭州下雨就打车从公司回家", {"intent": "weather_ride", "city": "杭州", "date": D["后天"], "origin": "公司", "dest": "家"}),
    ("帝都明天下雨的话，帮我从家叫车到虹桥火车站", {"intent": "weather_ride", "city": "北京", "date": D["明天"], "origin": "家", "dest": "虹桥火车站"}),
    ("杨国福有啥好吃的", {"intent": "food_menu", "restaurant": "杨国福麻辣烫", "dish": None}),
    ("沙县那家有没有扁肉", {"intent": "food_menu", "restaurant": "沙县小吃", "dish": "扁肉"}),
    ("一点点都有些啥喝的", {"intent": "food_menu", "restaurant": "一点点", "dish": None}),
    ("川味小馆今天能送吗，菜单给我看看", {"intent": "food_menu", "restaurant": "川味小馆", "dish": None}),
    ("老王家黄焖鸡有排骨饭不", {"intent": "food_menu", "restaurant": "老王黄焖鸡", "dish": "黄焖排骨饭"}),
    ("老王家黄焖鸡给我来个黄焖鸡米饭，钱直接付了", {"intent": "food_order", "restaurant": "老王黄焖鸡", "items": [{"name": "黄焖鸡米饭", "qty": 1}], "pay": True}),
    ("沙县整两份蒸饺一碗拌面", {"intent": "food_order", "restaurant": "沙县小吃", "items": [{"name": "蒸饺", "qty": 2}, {"name": "拌面", "qty": 1}], "pay": False}),
    ("一点点下单三杯柠檬绿茶，顺便付了", {"intent": "food_order", "restaurant": "一点点", "items": [{"name": "柠檬绿茶", "qty": 3}], "pay": True}),
    ("杨国福给我来一份炸串拼盘加一瓶酸梅汤，微信支付", {"intent": "food_order", "restaurant": "杨国福麻辣烫", "items": [{"name": "炸串拼盘", "qty": 1}, {"name": "酸梅汤", "qty": 1}], "pay": True}),
    ("川味小馆要个水煮鱼", {"intent": "food_order", "restaurant": "川味小馆", "items": [{"name": "水煮鱼", "qty": 1}], "pay": False}),
    ("帮我订份鸡腿饭，沙县的，付款", {"intent": "food_order", "restaurant": "沙县小吃", "items": [{"name": "鸡腿饭", "qty": 1}], "pay": True}),
    ("给我点杯芝芝莓莓", {"intent": "food_order", "restaurant": "一点点", "items": [{"name": "芝芝莓莓", "qty": 1}], "pay": False}),
    ("老王黄焖鸡点个排骨饭再来瓶可乐", {"intent": "food_order", "restaurant": "老王黄焖鸡", "items": [{"name": "黄焖排骨饭", "qty": 1}, {"name": "可乐", "qty": 1}], "pay": False}),
    ("从单位打车去机场大概多少钱", {"intent": "ride", "origin": "公司", "dest": "浦东机场"}),
    ("家到公司打个车要多少", {"intent": "ride", "origin": "家", "dest": "公司"}),
    ("机场打车回公司多少钱", {"intent": "ride", "origin": "浦东机场", "dest": "公司"}),
    ("帮我叫个车，从家去火车站", {"intent": "ride", "origin": "家", "dest": "虹桥火车站"}),
    ("从家走到地铁站要多久", {"intent": "route", "origin": "家", "dest": "地铁站", "mode": "walk"}),
    ("家到虹桥站开车怎么走", {"intent": "route", "origin": "家", "dest": "虹桥火车站", "mode": "drive"}),
    ("公司回家开车多远", {"intent": "route", "origin": "公司", "dest": "家", "mode": "drive"}),
    ("地铁站离家多远，走路", {"intent": "route", "origin": "地铁站", "dest": "家", "mode": "walk"}),
    ("明天上海下不下雨？下的话从公司叫车去浦东机场", {"intent": "weather_ride", "city": "上海", "date": D["明天"], "origin": "公司", "dest": "浦东机场"}),
    ("成都后天天气，顺便说下要不要带伞", {"intent": "weather", "city": "成都", "date": D["后天"]}),
    ("哈尔滨明天零下几度", {"intent": "weather", "city": "哈尔滨", "date": D["明天"]}),
    ("一点点两杯波霸奶茶，付钱", {"intent": "food_order", "restaurant": "一点点", "items": [{"name": "波霸奶茶", "qty": 2}], "pay": True}),
]

out = []
for f in ("testset.json", "holdout.json"):
    for c in json.loads((ROOT / "data" / f).read_text(encoding="utf-8")):
        out.append({"id": c["id"], "source": f.split(".")[0], "instruction": c["instruction"], "gold_plan": parse(c["instruction"])})
for i, (t, g) in enumerate(P):
    out.append({"id": f"PP{i + 1:02d}", "source": "paraphrase", "instruction": t, "gold_plan": g})
(ROOT / "data" / "parse_set.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(out), "parse cases;", len(P), "paraphrases")
