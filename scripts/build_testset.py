"""生成 data/testset.json（58 条指令，带故障注入计划与真值标签）。

字段：
  id / category / instruction / gold_intent
  fault_plan       {接口: [每次调用的故障, ...]}，用尽后为 ok；故障的具体数值由 Env 用固定种子抽样
  gt_anomalous     该指令执行中是否注入了任何故障（指令级）
  gt_types         注入的故障种类
  acceptable       视为「处置正确」的最终结局集合（ok / degraded / fallback / human / failed）
  why              为什么这样标
调用级真值（每次工具调用是否有故障）由 Env.gt 在运行时记录，评测器读取。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fbagent.parser import parse  # noqa: E402

C = []


def case(cid, cat, text, intent, plan=None, acceptable=("ok",), why=""):
    types = sorted({k for v in (plan or {}).values() for k in v if k != "ok"})
    C.append({"id": cid, "category": cat, "instruction": text, "gold_intent": intent,
              "fault_plan": plan or {}, "gt_anomalous": bool(types), "gt_types": types,
              "acceptable": list(acceptable), "why": why})


# ---- 正常（11）----
case("C01", "clean", "北京今天天气怎么样", "weather")
case("C02", "clean", "杭州明天冷不冷", "weather")
case("C03", "clean", "在沙县小吃点一份拌面", "food_order")
case("C04", "clean", "看看杨国福麻辣烫的菜单", "food_menu")
case("C05", "clean", "从家打车去公司多少钱", "ride")
case("C06", "clean", "从家到虹桥火车站的路线", "route")
case("C07", "clean", "在老王黄焖鸡点一份黄焖鸡米饭并付款", "food_order")
case("C08", "clean", "成都后天天气", "weather")
case("C09", "clean", "明天北京要是下雨就帮我从家叫车去公司", "weather_ride")
case("C10", "clean", "明天上海要是下雨就帮我从家叫车去公司", "weather_ride")
case("C11", "clean", "在杨国福麻辣烫点一份麻辣烫和一份酸梅汤，付款", "food_order")
# ---- 难负例：看着怪但是真的（8）----
case("H01", "hard_negative", "漠河明天天气怎么样，要穿多少", "weather", why="漠河 11 月最低 -32°C 是真实量级，触发 soft 规则")
case("H02", "hard_negative", "从公司打车去浦东机场多少钱", "ride", why="62km 机场单 221 元，触发 soft 规则")
case("H03", "hard_negative", "看看川味小馆的菜单", "food_menu", why="雨天高峰配送 95 分钟，商家已备注")
case("H04", "hard_negative", "一点点点二十杯芝芝莓莓，直接付款", "food_order", why="团单 476 元，触发 soft 规则")
case("H05", "hard_negative", "广州今天天气", "weather", why="广州 11 月 30°C 偏热但合理，规则不报，考 LLM 误报")
case("H06", "hard_negative", "从家步行到地铁站怎么走", "route", why="0.2km 3 分钟，考 LLM 误报")
case("H07", "hard_negative", "看看老王黄焖鸡的菜单", "food_menu", why="含 0 元赠品「免费加饭」")
case("H08", "hard_negative", "哈尔滨明天天气", "weather", why="-14°C 正常")
# ---- 传输类（8）----
case("T01", "transient", "上海明天天气怎么样", "weather", {"weather.query": ["timeout", "ok"]}, ("ok", "fallback"), "首次超时，重试即可")
case("T02", "transient", "看看沙县小吃的菜单", "food_menu", {"food.search": ["http_500", "ok"]}, ("ok", "fallback"))
case("T03", "transient", "深圳今天天气", "weather", {"weather.query": ["http_429", "ok"]}, ("ok", "fallback"))
case("T04", "transient", "杭州今天天气", "weather", {"weather.query": ["timeout", "timeout", "timeout"]}, ("fallback",), "持续超时，应切备用源")
case("T05", "transient", "看看一点点的菜单", "food_menu", {"food.search": ["timeout", "timeout", "timeout"]}, ("fallback",), "持续超时，应页面接力")
case("T06", "transient", "在沙县小吃点一份鸡腿饭", "food_order", {"food.order": ["timeout", "ok"]}, ("ok", "human"), "下单超时且未落单，带 token 重试安全")
case("T07", "transient", "在沙县小吃点一份蒸饺", "food_order", {"food.order": ["timeout_after_create", "ok"]}, ("ok", "human"), "服务端已落单但响应丢失；无 token 重试会重复下单")
case("T08", "transient", "北京明天天气", "weather", {"weather.query": ["http_500", "http_500", "http_500"]}, ("fallback",))
# ---- 结构类（3）----
case("S01", "schema", "上海今天天气", "weather", {"weather.query": ["schema_missing"]}, ("fallback",))
case("S02", "schema", "老王黄焖鸡有什么吃的", "food_menu", {"food.search": ["schema_type"]}, ("fallback",))
case("S03", "schema", "深圳明天天气", "weather", {"weather.query": ["schema_type"]}, ("fallback",))
# ---- 语义错误：规则能抓（7）----
case("R01", "semantic_rule", "广州明天天气", "weather", {"weather.query": ["sem_range_temp"]}, ("fallback",), "80°C 超物理范围")
case("R02", "semantic_rule", "成都今天天气", "weather", {"weather.query": ["sem_low_gt_high"]}, ("fallback",))
case("R03", "semantic_rule", "杭州后天天气", "weather", {"weather.query": ["sem_city"]}, ("fallback",), "回显城市不一致")
case("R04", "semantic_rule", "看看杨国福麻辣烫有什么", "food_menu", {"food.search": ["sem_eta_negative"]}, ("fallback",))
case("R05", "semantic_rule", "在老王黄焖鸡点一份黄焖鸡米饭", "food_order", {"food.search": ["sem_price_zero"]}, ("fallback", "human"), "主菜 0 元：soft 规则，严格版抓、宽松版漏")
case("R06", "semantic_rule", "在老王黄焖鸡点一份黄焖鸡米饭并付款", "food_order", {"food.search": ["sem_price_unit"]}, ("fallback", "human"), "25.8 变 258：soft 规则（>200）")
case("R07", "semantic_rule", "在沙县小吃点一份扁肉", "food_order", {"food.order": ["sem_qty"]}, ("human",), "订单数量 ×10，回显校验能抓")
# ---- 语义错误：规则 v1 抓不到（8）----
case("L01", "semantic_llm", "北京后天天气", "weather", {"weather.query": ["sem_condition_precip"]}, ("fallback",), "「晴」却有 20+mm 降水")
case("L02", "semantic_llm", "上海明天天气，要带伞吗", "weather", {"weather.query": ["sem_inrange_temp"]}, ("fallback",), "11 月上海 -17~-9°C")
case("L03", "semantic_llm", "广州后天天气", "weather", {"weather.query": ["sem_condition_season"]}, ("fallback",), "广州 30°C 下大雪")
case("L04", "semantic_llm", "看看杨国福麻辣烫的菜单", "food_menu", {"food.search": ["sem_wrong_menu"]}, ("fallback",), "麻辣烫店返回麦当劳菜单")
case("L05", "semantic_llm", "看看沙县小吃的菜单，多久能送到", "food_menu", {"food.search": ["sem_eta_implausible"]}, ("fallback",), "12.4km 送 3 分钟")
case("L06", "semantic_llm", "在沙县小吃点一份拌面并付款", "food_order", {"food.search": ["sem_price_unit"]}, ("fallback", "human"), "拌面 80 元，未过 200 阈值")
case("L07", "semantic_llm", "看看一点点的菜单", "food_menu", {"food.search": ["sem_price_unit"]}, ("fallback",), "奶茶 130 元")
case("L08", "semantic_llm", "明天杭州要是下雨就帮我从家叫车去公司", "weather_ride", {"weather.query": ["sem_condition_season"]}, ("fallback",), "杭州 15°C 下大雪，会误触发叫车")
# ---- 过期（3）----
case("ST01", "stale", "北京今天天气", "weather", {"weather.query": ["stale_hard"]}, ("fallback",), "3 天前的数据")
case("ST02", "stale", "成都明天天气", "weather", {"weather.query": ["stale_soft"]}, ("degraded", "fallback"), "5 小时前的数据，可降级展示")
case("ST03", "stale", "看看杨国福麻辣烫的菜单", "food_menu", {"food.search": ["stale_menu"]}, ("degraded", "fallback"), "菜单 40 天未更新")
# ---- 部分数据（2）----
case("P01", "partial", "沙县小吃有拌面吗", "food_menu", {"food.search": ["partial"]}, ("degraded", "fallback"), "分页截断，且要的菜不在")
case("P02", "partial", "看看川味小馆的菜单", "food_menu", {"food.search": ["partial"]}, ("degraded", "fallback"), "has_more=true 只返回 1 道，规则 v1 不查")
# ---- 支付（8）----
case("PAY01", "payment", "在沙县小吃点一份鸡腿饭并付款", "food_order", {"pay.create": ["timeout_after_charge"]}, ("ok", "human"), "已扣款但响应丢失；盲重试=重复扣款")
case("PAY02", "payment", "在杨国福麻辣烫点一份炸串拼盘并付款", "food_order", {"pay.create": ["timeout_before_charge"]}, ("ok", "human"), "未扣款，查单后同 key 重试")
case("PAY03", "payment", "在一点点点一杯柠檬绿茶并付款", "food_order", {"pay.create": ["http_500"]}, ("ok", "human"))
case("PAY04", "payment", "在老王黄焖鸡点一份黄焖排骨饭并付款", "food_order", {"pay.create": ["amount_mismatch"]}, ("human",), "实扣是应付的 10 倍")
case("PAY05", "payment", "在川味小馆点一份回锅肉并付款", "food_order", {"pay.create": ["timeout_after_charge"], "pay.query": ["processing"]}, ("human",), "查单仍处理中，必须等待/人工")
case("PAY06", "payment", "在沙县小吃点一份蒸饺并付款", "food_order", {"pay.create": ["timeout_before_charge", "timeout_before_charge"]}, ("ok", "human"), "同 key 重试仍超时 → 不再扣，转人工（无损的 ok 也算对）")
case("PAY07", "payment", "在一点点点两杯波霸奶茶并付款", "food_order", {"food.order": ["timeout_after_create"], "pay.create": ["timeout_after_charge"]}, ("ok", "human"), "下单和支付都丢响应")
case("PAY08", "payment", "在杨国福麻辣烫点一份麻辣烫并付款", "food_order", {"pay.create": ["http_429"]}, ("ok", "human"))

if __name__ == "__main__":
    bad = [(c["id"], parse(c["instruction"])["intent"]) for c in C if parse(c["instruction"])["intent"] != c["gold_intent"]]
    assert not bad, bad
    out = ROOT / "data" / "testset.json"
    out.write_text(json.dumps(C, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(len(C), "cases", dict(Counter(c["category"] for c in C)), "anomalous", sum(c["gt_anomalous"] for c in C))
