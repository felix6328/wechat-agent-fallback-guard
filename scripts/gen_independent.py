"""独立构造测试集·第 1 步：让另一个模型家族（智谱 GLM-4.5-Air）生成异常返回和难负例。

为什么：主测试集的故障是我自己写的注入器产生的，规则也是我写的，存在循环。这里换一个与判官
（DeepSeek、Qwen）不同家族的模型，只告诉它「接口是什么、正常返回长什么样」，让它自己想
真实后端会出的数据质量问题，以及「看着怪但其实正确」的返回。生成结果写入 data/gen_raw.json，
第 2 步（scripts/review_independent.py）人工逐条审核后才进入测试集。
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fbagent.envload import load_siliconflow_api_key  # noqa: E402
from fbagent.llm_judge import BASE_URL, _charge, cost_cny  # noqa: E402
from fbagent.mock_apis import Env  # noqa: E402
from fbagent.parser import parse  # noqa: E402
from fbagent import world as W  # noqa: E402

MODEL = "zai-org/GLM-4.5-Air"
SCEN = [  # (指令, 要替换返回的接口, 所在路径)
    ("北京今天天气怎么样", "weather.query", "display"),
    ("上海明天天气", "weather.query", "display"),
    ("广州后天天气", "weather.query", "display"),
    ("深圳今天天气如何", "weather.query", "display"),
    ("杭州明天天气", "weather.query", "display"),
    ("成都后天天气", "weather.query", "display"),
    ("哈尔滨今天天气", "weather.query", "display"),
    ("漠河明天天气", "weather.query", "display"),
    ("明天上海要是下雨就帮我从家叫车去公司", "weather.query", "decision"),
    ("看看老王黄焖鸡的菜单", "food.search", "display"),
    ("看看杨国福麻辣烫的菜单", "food.search", "display"),
    ("看看沙县小吃的菜单", "food.search", "display"),
    ("看看一点点的菜单", "food.search", "display"),
    ("看看川味小馆的菜单", "food.search", "display"),
    ("在沙县小吃点一份鸡腿饭", "food.search", "decision"),
    ("在杨国福麻辣烫点一份炸串拼盘并付款", "food.search", "decision"),
    ("在老王黄焖鸡点一份黄焖鸡米饭", "food.order", "write"),
    ("在一点点点两杯波霸奶茶并付款", "food.order", "write"),
]

PROMPT = """你在帮一个团队做「AI 助手调用小程序接口」的质量测试。下面是用户的一句话、助手调用的接口、请求参数，以及这个接口一次**正常**的返回 JSON。当前时间 2026-11-15 12:00（北京时间）。

用户原话：{ins}
接口：{op}
请求参数：{args}
正常返回：{data}

请构造 6 个这个接口的返回 JSON 变体：
- 4 个「有问题」的返回：模拟真实小程序后端会出的数据质量问题，要尽量多样、真实、有迷惑性（不要只是把数字改成离谱值；想想缓存、单位、时区、字段错位、串数据、分页、上下游不一致、默认值、编码等现实原因）。
- 2 个「看着不寻常但其实正确」的返回：数据和正常返回不同、可能让人起疑，但在现实中完全合理。
要求：保持字段名和整体结构与正常返回一致（除非问题本身就是字段缺失/类型错误）；每个变体都给出完整 JSON。
只输出一个 JSON 对象：{{"variants": [{{"label": "anomalous" 或 "normal", "type": "semantic_wrong|context_mismatch|stale|partial|schema_error|none", "description": "一句话说明问题或为什么其实正确", "data": {{...}}}}]}}"""


def main():
    key = load_siliconflow_api_key()
    out = []
    for i, (ins, op, path) in enumerate(SCEN):
        plan = parse(ins)
        env = Env(f"gen{i}", {}, seed=42)
        from fbagent.agent import Agent
        res = Agent("naive").run(ins, env, f"gen{i}")
        call = next(c for c in env.calls if c.op == op)
        msg = PROMPT.format(ins=ins, op=op, args=json.dumps(call.args, ensure_ascii=False),
                            data=json.dumps(call.data, ensure_ascii=False))
        body = {"model": MODEL, "messages": [{"role": "user", "content": msg}], "temperature": 0.9,
                "max_tokens": 4000, "enable_thinking": False}
        _charge(0.0)
        t0 = time.perf_counter()
        resp = json.load(urllib.request.urlopen(urllib.request.Request(
            BASE_URL, data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}), timeout=180))
        u = resp.get("usage", {})
        c = cost_cny(MODEL, u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        _charge(c)
        with open(ROOT / "data" / "cost" / "llm.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "model": MODEL, "purpose": "gen_testset",
                                "prompt_tokens": u.get("prompt_tokens", 0), "completion_tokens": u.get("completion_tokens", 0),
                                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}) + "\n")
        try:
            txt = resp["choices"][0]["message"]["content"]
            vs = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])["variants"]
        except Exception as e:
            print("parse fail", ins, e)
            vs = []
        for j, v in enumerate(vs):
            out.append({"gid": f"G{i:02d}-{j}", "instruction": ins, "op": op, "path": path, "args": call.args,
                        "clean": call.data, **v})
        print(i, ins, len(vs), f"¥{c:.4f}")
    (ROOT / "data" / "gen_raw.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(out), "variants")


if __name__ == "__main__":
    main()
