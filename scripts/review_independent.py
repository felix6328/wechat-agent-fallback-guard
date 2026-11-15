"""人工审核 GLM-4.5-Air 生成的变体 → data/independent.json。

审核原则（逐条看过 gen_raw.json 的字段 diff 后定的）：
1. 只保留「内容」类问题与难负例。纯格式漂移（数字变字符串、时间戳少时区、字段缺失但对用户无害）剔除：
   这类问题由 schema 校验覆盖，主测试集已经测过，放进来只会抬高规则分数。
2. 生成模型给的标签不可信的，按产品语义改标（例：价格以「分」返回却标成正常 → 改为错误数据）。
3. 产品策略本身有争议的剔除（例：下单金额比菜单价低/高几毛、30 分钟后的「未来」时间戳、分店算不算同一家）。
4. 生成内容与正常返回完全相同的剔除。
类型映射：wrong = 错误数据（只能兜底，不能展示）；stale / partial = 可带提示降级或兜底；clean = 难负例，应正常放行。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# gid → (决定, 理由)。决定 ∈ wrong / stale / partial / clean / reject
R = {
    "G00-0": ("wrong", "日期返回 11-10，与请求不符（不是单纯过期）"), "G00-1": ("wrong", "华氏度冒充摄氏度"),
    "G00-2": ("wrong", "串城市：上海"), "G00-3": ("reject", "纯格式：降水量字符串"),
    "G00-4": ("clean", "UTC 时间戳，换算后一致"), "G00-5": ("clean", "数据源名称变化，内容一致"),
    "G01-0": ("stale", "前一天更新的缓存"), "G01-1": ("wrong", "数值换成别的城市但城市字段正确（几乎不可检测，保留以示天花板）"),
    "G01-2": ("wrong", "华氏度"), "G01-3": ("partial", "降水为 null"),
    "G01-4": ("clean", "UTC 时间戳"), "G01-5": ("clean", "数据源名称变化"),
    "G02-0": ("stale", "前一天更新"), "G02-1": ("wrong", "串城市：深圳"), "G02-2": ("wrong", "华氏度"),
    "G02-3": ("partial", "缺降水字段"), "G02-4": ("clean", "降水 0.1 的正常更新"), "G02-5": ("clean", "UTC 时间戳"),
    "G03-0": ("stale", "前一天数据"), "G03-1": ("wrong", "华氏度"), "G03-2": ("reject", "纯格式：时间戳缺时区"),
    "G03-3": ("wrong", "晴天却有 10mm 降水（单位错）"), "G03-4": ("clean", "数据源 v2、12:00 更新"),
    "G03-5": ("clean", "城市/天气附带英文"),
    "G04-0": ("stale", "10 月 1 日的旧数据"), "G04-1": ("reject", "纯格式：温度带单位字符串"),
    "G04-2": ("wrong", "数值换成上海的（城市字段正确）"), "G04-3": ("partial", "降水为 null"),
    "G04-4": ("clean", "UTC 时间戳"), "G04-5": ("clean", "杭州市/阴天/秒级时间戳：同义改写"),
    "G05-0": ("stale", "前一天数据"), "G05-1": ("wrong", "串城市：北京"), "G05-2": ("wrong", "华氏度"),
    "G05-3": ("partial", "缺降水字段"), "G05-4": ("clean", "UTC 时间戳"), "G05-5": ("reject", "与正常返回完全相同"),
    "G06-0": ("wrong", "日期返回前一天"), "G06-1": ("wrong", "华氏度"), "G06-2": ("wrong", "多云却 20mm 降水"),
    "G06-3": ("wrong", "数值换成别的城市（哈尔滨 11 月高温 8°C 仍可能，难检测）"),
    "G06-4": ("clean", "UTC 时间戳"), "G06-5": ("clean", "另一服务商，数值小幅偏差"),
    "G07-0": ("stale", "前一天数据"), "G07-1": ("wrong", "漠河 11 月 15°C/8°C，季节不符"), "G07-2": ("wrong", "华氏度"),
    "G07-3": ("partial", "缺降水字段"), "G07-4": ("clean", "12:00 新预报，小幅变化"), "G07-5": ("clean", "阵雪、v2 数据源，小幅变化"),
    "G08-0": ("stale", "前一天数据，且会把小雨变成晴 → 误不叫车"), "G08-1": ("wrong", "小雨却 65mm（单位错）"),
    "G08-2": ("wrong", "串城市：北京"), "G08-3": ("reject", "纯格式：温度字符串"),
    "G08-4": ("reject", "更新时间是 30 分钟后的未来时间，是否算异常有争议"), "G08-5": ("clean", "UTC 时间戳"),
    "G09-0": ("wrong", "价格带美元符号展示给用户"), "G09-1": ("stale", "昨天的菜单，价格已变"),
    "G09-2": ("wrong", "菜品串成另一家店"), "G09-3": ("clean", "生成模型标为异常，实为等价的 UTC 时间戳 → 改标正常"),
    "G09-4": ("wrong", "生成模型标为正常，实为以「分」返回的价格（2580 元一份黄焖鸡）→ 改标错误"),
    "G09-5": ("clean", "note 为 null"),
    "G10-0": ("stale", "5 天前的菜单且价格已变"), "G10-1": ("wrong", "菜品串成兰州拉面"), "G10-2": ("wrong", "价格为美元数值"),
    "G10-3": ("reject", "has_more=true 但数据完整，对展示影响有争议"), "G10-4": ("reject", "距离英里冒充公里，影响轻微有争议"),
    "G10-5": ("clean", "UTC 时间戳"),
    "G11-0": ("reject", "只有时间戳变成昨天，数据与真值一致，无害"), "G11-1": ("wrong", "返回肯德基"),
    "G11-2": ("wrong", "价格以分返回"), "G11-3": ("partial", "只返回 2 道菜，has_more=true"),
    "G11-4": ("clean", "高峰期 45 分钟"), "G11-5": ("clean", "距离 5.2km、38 分钟，合理"),
    "G12-0": ("stale", "5 天前菜单，波霸奶茶 33 元"), "G12-1": ("wrong", "返回喜茶菜单"),
    "G12-2": ("partial", "菜单被截断且 has_more 没标（几乎不可检测）"), "G12-3": ("wrong", "配送 2.5 分钟（小时当分钟）"),
    "G12-4": ("clean", "已打烊、空菜单：应如实告知，不该当故障兜底"), "G12-5": ("clean", "新增特价商品"),
    "G13-0": ("reject", "只有时间戳变成昨天，数据一致，无害"), "G13-1": ("wrong", "返回披萨店菜单"),
    "G13-2": ("wrong", "配送 1.6 分钟（小时当分钟）"), "G13-3": ("reject", "缺 has_more/note，对用户无害"),
    "G13-4": ("reject", "与正常返回完全相同"), "G13-5": ("clean", "路况导致小幅波动"),
    "G14-0": ("partial", "旧菜单里没有要点的鸡腿饭"), "G14-1": ("partial", "price_cny 字段名拼错，下单拿不到价格"),
    "G14-2": ("wrong", "返回肯德基"), "G14-3": ("reject", "纯格式：eta 字符串"),
    "G14-4": ("clean", "鸡腿饭调价到 16.5"), "G14-5": ("clean", "配送 25 分钟"),
    "G15-0": ("stale", "昨天菜单，价格已变，会按旧价下单"), "G15-1": ("reject", "分店算不算同一家，产品策略有争议"),
    "G15-2": ("wrong", "价格以分返回"), "G15-3": ("partial", "数据加载中、字段默认值、菜单被截断"),
    "G15-4": ("clean", "新用户特惠"), "G15-5": ("clean", "UTC 时间戳"),
    "G16-0": ("wrong", "下单返回的是上一笔已送达订单"), "G16-1": ("wrong", "串单：别人的订单"),
    "G16-2": ("reject", "纯格式：价格字符串"), "G16-3": ("reject", "下单回执缺 eta，对用户无害"),
    "G16-4": ("wrong", "生成模型标为正常，eta=-480 显然错误 → 改标错误"),
    "G16-5": ("reject", "实扣金额与菜单不一致，按产品策略应转人工还是放行有争议"),
    "G17-0": ("wrong", "新订单状态却是已完成"), "G17-1": ("wrong", "订单变成喜茶"),
    "G17-2": ("wrong", "金额按美元数值返回，与应付不一致"), "G17-3": ("partial", "回执缺单价和 eta"),
    "G17-4": ("clean", "eta 15 分钟"), "G17-5": ("reject", "促销价低于菜单价，是否转人工有争议"),
}


def acceptable(dec, op, path):
    if dec == "clean":
        return ["ok", "degraded"] if op == "food.search" and path == "display" else ["ok"]
    if op == "food.order":
        return ["human"]
    if path == "decision":
        return ["fallback", "human"] + (["degraded"] if dec != "wrong" and op == "food.search" else [])
    return ["fallback"] if dec == "wrong" else ["degraded", "fallback"]


def main():
    raw = json.loads((ROOT / "data/gen_raw.json").read_text(encoding="utf-8"))
    assert set(R) == {v["gid"] for v in raw}, set(R) ^ {v["gid"] for v in raw}
    cases, review = [], []
    for v in raw:
        dec, why = R[v["gid"]]
        relabel = (dec == "clean") != (v["label"] == "normal") and dec != "reject"
        review.append({"gid": v["gid"], "gen_label": v["label"], "gen_type": v["type"], "gen_description": v["description"],
                       "decision": dec, "relabeled": relabel, "reason": why})
        if dec == "reject":
            continue
        spec = {"kind": f"gen_{dec}", "data": v["data"]}
        rep = 1 if v["op"] == "food.order" else 3   # 读接口的内容问题在重试时依然存在
        cases.append({"id": "I" + v["gid"][1:], "category": "ind_" + ("clean" if dec == "clean" else dec),
                      "instruction": v["instruction"], "intent": None,
                      "fault_plan": {v["op"]: [spec] * rep}, "gt_anomalous": dec != "clean",
                      "acceptable": acceptable(dec, v["op"], v["path"]),
                      "why": f"[GLM-4.5-Air 生成·人工审核] {why}"})
    from fbagent.parser import parse  # noqa
    for c in cases:
        c["intent"] = parse(c["instruction"])["intent"]
    (ROOT / "data/independent.json").write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / "data/gen_review.json").write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(len(raw), "生成 →", len(cases), "保留；", Counter(r["decision"] for r in review),
          "改标", sum(r["relabeled"] for r in review))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    main()
