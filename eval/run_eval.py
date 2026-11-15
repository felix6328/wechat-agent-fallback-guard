"""主评测：测试集 × 配置 × 多个种子，报告均值与 95% bootstrap 区间（按指令整簇重抽样）。

用法：
  FB_ENV_FILE=/path/.env python eval/run_eval.py                                   # 主测试集，3 个种子，全部配置
  FB_ENV_FILE=/path/.env python eval/run_eval.py --testset data/holdout.json --tag _holdout
  FB_ENV_FILE=/path/.env python eval/run_eval.py --testset data/independent.json --tag _independent --seeds 42
  python eval/run_eval.py --no-llm                                                 # 只跑不需要模型的配置
种子影响：故障数值、虚拟时延、时间戳 → LLM 看到的 prompt 也不同。LLM 结果有磁盘缓存，重跑不计费。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fbagent.configs import CONFIGS, judge, new_cache  # noqa: E402
from fbagent.evaluate import run_case, summarize  # noqa: E402
from fbagent.llm_judge import PRICES  # noqa: E402


def f3(x):
    return "—" if x is None else f"{x:.3f}"


def ci(s, k, nd=3, scale=1.0):
    m = s[k]
    lo, hi = s["ci95"].get(k, (None, None))
    if m is None:
        return "—"
    if lo is None or len(s["seeds"]) == 0:
        return f"{m * scale:.{nd}f}"
    return f"{m * scale:.{nd}f} [{lo * scale:.{nd}f}, {hi * scale:.{nd}f}]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--testset", default="data/testset.json")
    ap.add_argument("--tag", default="")
    ap.add_argument("--seeds", default="42,7,2026")
    ap.add_argument("--only", default="", help="逗号分隔的配置 key")
    a = ap.parse_args()
    seeds = [int(x) for x in a.seeds.split(",")]
    cases = json.loads((ROOT / a.testset).read_text(encoding="utf-8"))
    only = set(a.only.split(",")) if a.only else None
    rows_all, S = [], {}
    t0 = time.time()
    for cfg in CONFIGS:
        key, name, variant, jname, rv, asyn, use_cache = cfg
        if only and key not in only:
            continue
        if jname and a.no_llm:
            continue
        j = judge(jname) if jname else None
        if j is not None and not j.available:
            print("缺少 SILICONFLOW_API_KEY，跳过", name)
            continue
        vc = new_cache(cfg)
        rows = []
        for sd in seeds:   # 种子顺序执行：判定缓存在种子之间保留，模拟重复流量
            with ThreadPoolExecutor(max_workers=a.workers if j else 1) as ex:
                rows += list(ex.map(lambda c: run_case(c, variant, j, rv, seed=sd, async_display=asyn,
                                                       verdict_cache=vc), cases))
        for r in rows:
            r["config"], r["config_key"] = name, key
        S[key] = {"name": name, **summarize(rows)}
        s = S[key]
        print(f"[{key}] {name}: 召回 {f3(s['recall'])} 精确 {f3(s['precision'])} 兜底 {f3(s['fallback_success'])} "
              f"放行 {f3(s['clean_pass'])} 受损率 {f3(s['harm_rate'])} P50 {s['latency_p50']:.0f}ms "
              f"¥/千次 {s['cost_per_1k']:.2f} ({time.time() - t0:.0f}s)", flush=True)
        rows_all += rows
    out = ROOT / "eval"
    (out / f"results{a.tag}.json").write_text(json.dumps(
        {"testset": a.testset, "seeds": seeds, "n_cases": len(cases), "summaries": S, "prices": PRICES,
         "generated_at": time.strftime("%Y-%m-%d %H:%M:%S %z")}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    with open(out / f"traces{a.tag}.jsonl", "w", encoding="utf-8") as f:
        for r in rows_all:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    write_md(a, cases, seeds, rows_all, S)
    write_badcases(a, rows_all)


def write_md(a, cases, seeds, rows, S):
    n_anom = sum(c["gt_anomalous"] for c in cases)
    L = [f"# 评测结果：`{a.testset}`（自动生成，勿手改）\n",
         f"生成时间 {time.strftime('%Y-%m-%d %H:%M')}（Asia/Shanghai）。{len(cases)} 条指令（注入故障 {n_anom}，正常 {len(cases) - n_anom}，"
         f"其中难负例 {sum(c['category'] == 'hard_negative' for c in cases)}）× 种子 {seeds}。\n",
         "数值 = 所有种子合并后的点估计；方括号 = 95% bootstrap 区间（按指令整簇重抽样 1000 次）。"
         "模拟环境、合成数据；服务时延为虚拟毫秒；LLM 时延为真实公网 API 往返（并发 6，磁盘缓存命中时回放首次时延）；"
         "费用 = 返回 token × 硅基流动标价（查阅 2026-11-15），不是账单。\n",
         "## 1. 识别与处置\n",
         "| 配置 | 内容异常召回 | 精确率 | 误报率 | 兜底成功率 | 正常放行率 | 用户受损率 | 重复扣款/下单 |",
         "|---|---|---|---|---|---|---|---|"]
    for k, s in S.items():
        L.append(f"| {s['name']} | {ci(s, 'recall')} | {ci(s, 'precision')} | {ci(s, 'fpr')} | {ci(s, 'fallback_success')} | "
                 f"{ci(s, 'clean_pass')} | {ci(s, 'harm_rate')} | {s['dup_charge']}/{s['dup_order']} |")
    L += ["\n## 2. 时延与成本（用户感知时延 = 解析 + 服务 + 退避 + 同步 LLM；异步复核不计入首答）\n",
          "| 配置 | P50 ms | P95 ms | LLM 调用/条 | 缓存命中 | 升级次数 | 先展示后更正的指令占比 | ¥ / 千条 |",
          "|---|---|---|---|---|---|---|---|"]
    for k, s in S.items():
        L.append(f"| {s['name']} | {ci(s, 'latency_p50', 0)} | {s['latency_p95']:.0f} | {s['llm_calls_per_case']:.2f} | "
                 f"{s['cache_hits']} | {s['escalations']} | {f3(s['corrected_rate'])} | {ci(s, 'cost_per_1k', 2)} |")
    L += ["\n## 3. 种子间标准差（每个种子单独算指标，再求标准差）\n",
          "| 配置 | 召回 | 兜底成功率 | 正常放行率 | 受损率 |", "|---|---|---|---|---|"]
    for k, s in S.items():
        sd = s["seed_std"]
        L.append(f"| {s['name']} | {f3(sd['recall'])} | {f3(sd['fallback_success'])} | {f3(sd['clean_pass'])} | {f3(sd['harm_rate'])} |")
    cats = list(dict.fromkeys(c["category"] for c in cases))
    L += ["\n## 4. 分类别处置正确数（合并全部种子）\n", "| 配置 | " + " | ".join(cats) + " |", "|---|" + "---|" * len(cats)]
    for k, s in S.items():
        rs = [r for r in rows if r["config_key"] == k]
        L.append(f"| {s['name']} | " + " | ".join(
            f"{sum(r['correct'] for r in rs if r['category'] == c)}/{sum(r['category'] == c for r in rs)}" for c in cats) + " |")
    L += ["\n## 5. 混淆矩阵（内容调用，合并全部种子）\n", "| 配置 | TP | FP | FN | TN |", "|---|---|---|---|---|"]
    for k, s in S.items():
        c = s["confusion"]
        L.append(f"| {s['name']} | {c['tp']} | {c['fp']} | {c['fn']} | {c['tn']} |")
    L += ["\n指标定义：召回/精确/误报率为调用级，只统计拿到返回体的调用；兜底成功率 = 有故障的指令中结局在可接受集合内、没有暴露错误数据、没有重复扣款/下单、"
          "也没有「先展示后更正」；用户受损率 = 错误数据被当作事实展示且未更正（或旧/缺数据未提示），或重复扣款/下单。\n"]
    (ROOT / "eval" / f"results{a.tag}.md").write_text("\n".join(L), encoding="utf-8")


def write_badcases(a, rows):
    L = [f"# Badcase：`{a.testset}`（自动生成）\n", "每个配置只列种子 42 的处置错误，避免重复。\n"]
    by = defaultdict(list)
    for r in rows:
        if r["seed"] == rows[0]["seed"]:
            by[r["config"]].append(r)
    for name, rs in by.items():
        bad = [r for r in rs if not r["correct"]]
        L.append(f"\n## {name}（处置错误 {len(bad)}/{len(rs)}）\n")
        for r in bad:
            why = []
            if r["exposure"]:
                why.append("暴露错误数据 " + ",".join(str(e["fault"]) for e in r["exposure"]))
            if r["corrected"]:
                why.append("先展示后更正")
            if r["harmful"]:
                why.append(f"重复扣款={r['harm']['duplicate_charge']} 重复下单={r['harm']['duplicate_order']}")
            if r["outcome"] not in r["acceptable"]:
                why.append(f"结局 {r['outcome']} ∉ {r['acceptable']}")
            L.append(f"- **{r['id']}** {r['instruction']} — 注入 {r['injected'] or '无'}；{'；'.join(why)}")
            for c in r["calls"]:
                if c["content_call"] and c["pred"] != c["gt_content_anomaly"]:
                    kind = "FN 漏报" if c["gt_content_anomaly"] else "FP 误报"
                    L.append(f"  - {kind} #{c['call_id']} `{c['op']}` 真值={c['gt_fault']} 判定={c['pred_type']}（{c['source']}）{c['evidence']}")
    (ROOT / "eval" / f"badcases{a.tag}.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
