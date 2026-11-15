"""留出集 data/holdout.json（30 条：v1 的 17 条 + v2 新增 13 条）：在看到主测试集 badcase、写 prompt v2 之后另写的新措辞 / 新城市 / 新组合。
用途：检查 prompt v2 的改进是不是只在主测试集上成立（防止对测试集过拟合）。
H-U01 是故意放进去的「不可检测」样本：错误值对该城市季节仍然合理，任何质检都不该指望抓到。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import build_testset as bt  # noqa: E402
from fbagent.parser import parse  # noqa: E402

bt.C.clear()
case = bt.case
case("HC01", "clean", "后天杭州会下雨吗？下的话从公司叫车回家", "weather_ride")
case("HC02", "clean", "如果明天成都下雨，就从家叫车去虹桥火车站", "weather_ride")
case("HC03", "clean", "沙县小吃点两份蒸饺，付款", "food_order")
case("HC04", "clean", "深圳后天天气怎么样", "weather")
case("HN01", "hard_negative", "漠河今天冷吗", "weather")
case("HN02", "hard_negative", "从浦东机场打车去公司多少钱", "ride")
case("HN03", "hard_negative", "在川味小馆点一份水煮鱼和一份米饭", "food_order")
case("HL01", "semantic_llm", "如果后天上海下雨就从公司叫车回家", "weather_ride", {"weather.query": ["sem_condition_precip"]}, ("fallback",), "晴+大降水，会漏叫车")
case("HL02", "semantic_llm", "看看沙县小吃的菜单", "food_menu", {"food.search": ["sem_wrong_menu"]}, ("fallback",))
case("HL03", "partial", "一点点有什么喝的", "food_menu", {"food.search": ["partial"]}, ("degraded", "fallback"))
case("HL04", "semantic_llm", "深圳明天天气", "weather", {"weather.query": ["sem_condition_season"]}, ("fallback",))
case("HL05", "semantic_llm", "成都后天天气", "weather", {"weather.query": ["sem_condition_precip"]}, ("fallback",))
case("HL06", "semantic_llm", "看看老王黄焖鸡的菜单，多久送到", "food_menu", {"food.search": ["sem_eta_implausible"]}, ("fallback",))
case("HR01", "semantic_rule", "在杨国福麻辣烫点一份酸梅汤并付款", "food_order", {"food.search": ["sem_price_unit"]}, ("fallback", "human"), "主菜 320 元（soft）")
case("HR02", "semantic_rule", "在老王黄焖鸡点一份可乐", "food_order", {"food.order": ["sem_qty"]}, ("human",))
case("HP01", "payment", "在一点点点一杯芝芝莓莓并付款", "food_order", {"pay.create": ["timeout_after_charge"]}, ("ok", "human"))
case("H-U01", "undetectable", "哈尔滨后天天气", "weather", {"weather.query": ["sem_inrange_temp"]}, ("fallback",), "-17~-9°C 对哈尔滨 11 月仍合理：不可检测样本")

# ---- v2 新增 13 条（深度优化时补写，覆盖更多类别；同样在看主测试集结果之后写）----
case("HC05", "clean", "从家步行到地铁站要走多久", "route")
case("HC06", "clean", "在一点点点三杯柠檬绿茶", "food_order")
case("HN04", "hard_negative", "从公司打车去浦东机场", "ride", why="机场长途车费，soft 规则")
case("HN05", "hard_negative", "一点点点二十杯波霸奶茶并付款", "food_order", why="团单 260 元，不触发规则；考 LLM 误报")
case("HT01", "transient", "哈尔滨今天天气", "weather", {"weather.query": ["http_500", "ok"]}, ("ok", "fallback"))
case("HT02", "transient", "看看川味小馆有什么菜", "food_menu", {"food.search": ["timeout", "timeout", "timeout"]}, ("fallback",))
case("HS01", "schema", "成都明天天气", "weather", {"weather.query": ["schema_missing"]}, ("fallback",))
case("HST01", "stale", "杭州明天天气", "weather", {"weather.query": ["stale_hard"]}, ("fallback",))
case("HST02", "stale", "看看沙县小吃的菜单", "food_menu", {"food.search": ["stale_menu"]}, ("degraded", "fallback"))
case("HR03", "semantic_rule", "北京明天天气", "weather", {"weather.query": ["sem_city"]}, ("fallback",))
case("HL07", "semantic_llm", "看看一点点的菜单，几分钟能到", "food_menu", {"food.search": ["sem_eta_implausible"]}, ("fallback",))
case("HP02", "payment", "在老王黄焖鸡点一份黄焖鸡米饭并付款", "food_order", {"pay.create": ["amount_mismatch"]}, ("human",))
case("HP03", "payment", "在杨国福麻辣烫点一份酸梅汤并付款", "food_order", {"food.order": ["timeout_after_create"], "pay.create": ["timeout_before_charge"]}, ("ok", "human"))

bad = [(c["id"], parse(c["instruction"])) for c in bt.C if parse(c["instruction"])["intent"] != c["gold_intent"]]
assert not bad, bad
(ROOT / "data" / "holdout.json").write_text(json.dumps(bt.C, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(bt.C), "holdout cases")
