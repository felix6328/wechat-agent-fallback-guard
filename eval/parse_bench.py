"""指令解析基准：词表 vs LLM function-calling vs LLM+词表兜底。

金标：testset/holdout 的 88 条沿用（人工核对过的）词表解析结果；PP01–PP36 为手写的口语化改写，金标手工标注。
指标：计划完全一致（exact match）的比例；LLM 时延为真实 API 往返（缓存命中回放首次时延）；费用按标价估算。
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fbagent.llm_parser import LLMParser  # noqa: E402
from fbagent.parser import parse  # noqa: E402

MODELS = {"V4-Flash": "deepseek-ai/DeepSeek-V4-Flash", "Qwen2.5-7B": "Qwen/Qwen2.5-7B-Instruct"}


def same(a, b):
    return json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return 0
    k = (len(xs) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def main():
    cases = json.loads((ROOT / "data/parse_set.json").read_text(encoding="utf-8"))
    groups = {"原测试集+留出集（88）": [c for c in cases if c["source"] != "paraphrase"],
              "口语化改写（36）": [c for c in cases if c["source"] == "paraphrase"], "全部（124）": cases}
    res, rows = {}, {}
    t0 = time.perf_counter()
    word = {c["id"]: parse(c["instruction"]) for c in cases}
    word_ms = (time.perf_counter() - t0) * 1000 / len(cases)
    for mname, model in MODELS.items():
        p = LLMParser(model)
        with ThreadPoolExecutor(6) as ex:
            out = list(ex.map(lambda c: p.parse(c["instruction"]), cases))
        rows[mname] = {c["id"]: o for c, o in zip(cases, out)}
    L = ["# 指令解析基准（自动生成）\n",
         f"生成时间 {time.strftime('%Y-%m-%d %H:%M')}（Asia/Shanghai）。exact match = 解析出的计划与金标完全一致。"
         "「LLM 单独」= LLM 输出未通过词表校验时记为错；「LLM+兜底」= 校验失败时退回词表解析（线上实际用法）。\n",
         "| 方法 | " + " | ".join(groups) + " | 兜底触发 | P50 ms | P95 ms | ¥/千条 |", "|---|" + "---|" * (len(groups) + 4)]
    acc = lambda pred, cs: sum(same(pred(c), c["gold_plan"]) for c in cs)
    L.append("| 词表规则 | " + " | ".join(f"{acc(lambda c: word[c['id']], cs)}/{len(cs)}" for cs in groups.values())
             + f" | — | {word_ms:.2f} | — | 0 |")
    for mname in MODELS:
        r = rows[mname]
        lat = [r[c["id"]][2] for c in cases]
        cost = 1000 * sum(r[c["id"]][3] for c in cases) / len(cases)
        nfb = sum(r[c["id"]][1] == "fallback" for c in cases)
        only = lambda c: r[c["id"]][0] if r[c["id"]][1] == "llm" else None
        both = lambda c: r[c["id"]][0]
        L.append(f"| {mname} 单独 | " + " | ".join(f"{acc(only, cs)}/{len(cs)}" for cs in groups.values())
                 + f" | — | {pct(lat, 50):.0f} | {pct(lat, 95):.0f} | {cost:.2f} |")
        L.append(f"| {mname} + 词表兜底 | " + " | ".join(f"{acc(both, cs)}/{len(cs)}" for cs in groups.values())
                 + f" | {nfb} | {pct(lat, 50):.0f} | {pct(lat, 95):.0f} | {cost:.2f} |")
        res[mname] = {"fallbacks": nfb, "p50": pct(lat, 50), "p95": pct(lat, 95), "cost_per_1k": cost,
                      **{g: acc(both, cs) for g, cs in groups.items()},
                      **{g + "_only": acc(only, cs) for g, cs in groups.items()}}
    res["word"] = {g: acc(lambda c: word[c["id"]], cs) for g, cs in groups.items()}
    L.append("\n## 错例（V4-Flash + 兜底 与 词表规则）\n")
    for c in cases:
        w, v = word[c["id"]], rows["V4-Flash"][c["id"]]
        if not same(w, c["gold_plan"]) or not same(v[0], c["gold_plan"]):
            L.append(f"- **{c['id']}** {c['instruction']}\n  - 金标 `{json.dumps(c['gold_plan'], ensure_ascii=False)}`\n"
                     f"  - 词表 {'✓' if same(w, c['gold_plan']) else '✗ `' + json.dumps(w, ensure_ascii=False) + '`'}\n"
                     f"  - V4F（{v[1]}）{'✓' if same(v[0], c['gold_plan']) else '✗ `' + json.dumps(v[0], ensure_ascii=False) + '`'}")
    (ROOT / "eval/parse_results.md").write_text("\n".join(L), encoding="utf-8")
    (ROOT / "eval/parse_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(L[:8]))


if __name__ == "__main__":
    main()
