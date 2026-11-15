"""时延 / 成本 / 效果权衡图：eval/results*.json → docs/tradeoff.png 与 eval/tradeoff.md（不调 API）。"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
for fam in ("Noto Sans CJK SC", "Noto Serif CJK SC", "WenQuanYi Zen Hei"):
    if any(fam in f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = fam
        break
plt.rcParams["axes.unicode_minus"] = False

sys.path.insert(0, str(ROOT))
from fbagent.evaluate import point_metrics  # noqa: E402

SETS = [("results.json", "主测试集（58 条 × 3 种子）"), ("results_independent.json", "独立生成集（90 条，GLM 生成 + 人工审核）"),
        ("results_holdout.json", "留出集（30 条 × 3 种子）")]
SHORT = {"A": "A 无检测", "B1": "B1 规则宽松", "B2": "B2 规则严格", "E": "E 规则+蒸馏", "H7": "H 7B", "HF": "H V4F",
         "H32": "H V3.2", "DF": "纯LLM V4F", "C7": "级联 7B→V3.2", "CF": "级联 V4F→V3.2", "TF": "分层 V4F", "TFC": "分层+缓存(热)", "TFC0": "分层+缓存(冷)", "T32": "分层 V3.2", "T32C": "分层+缓存 V3.2(热)", "T32C0": "分层+缓存 V3.2(冷)"}


def cold_point(f, S, key="TFC"):
    """判定缓存在种子之间保留，后两个种子几乎全命中（同一指令、同一小时）。这里单独算第一个种子（冷缓存）。"""
    tr = ROOT / "eval" / f.replace("results", "traces").replace(".json", ".jsonl")
    if key not in S or not tr.exists():
        return None
    rows = [json.loads(l) for l in open(tr, encoding="utf-8")]
    first = min(rows, key=lambda r: 0)["seed"]
    rs = [r for r in rows if r.get("config_key") == key and r["seed"] == first]
    m = point_metrics(rs)
    m["name"] = S[key]["name"] + f"·冷缓存（只算第一个种子 {first}）"
    m["cache_hits"] = sum(r["cache_hits"] for r in rs)
    return m


def main():
    avail = [(f, t) for f, t in SETS if (ROOT / "eval" / f).exists()]
    fig, axes = plt.subplots(len(avail), 1, figsize=(10, 5.2 * len(avail)), squeeze=False)
    md = ["# 时延 / 成本 / 效果权衡（自动生成：python scripts/plot_tradeoff.py）\n",
          "横轴 = 用户感知时延 P50（解析 + 服务 + 退避 + 同步 LLM；分层方案的异步复核不计入首答）；纵轴 = 用户受损率（越低越好）。"
          "「更正率」= 先展示、后发【更正】的指令占比——分层方案用它换时延。\n"]
    PLOT = ["A", "B2", "E", "H7", "HF", "H32", "CF", "TF", "TFC", "T32", "T32C", "T32C0"]
    OFF = {"HF": (6, -12), "CF": (6, 8), "TF": (-70, 6), "TFC0": (6, -14), "TFC": (6, 4), "T32": (-80, -12), "T32C": (6, -12), "T32C0": (6, 10), "H7": (6, 6), "E": (6, -10)}
    for ax, (f, title) in zip(axes[:, 0], avail):
        S = json.loads((ROOT / "eval" / f).read_text(encoding="utf-8"))["summaries"]
        for ck in ("TFC", "T32C"):
            c0 = cold_point(f, S, ck)
            if c0:
                S[ck + "0"] = c0
        md += [f"\n## {title}\n", "| 配置 | P50 ms | P95 ms | 受损率 | 更正率 | 兜底成功率 | 正常放行率 | ¥/千条 |", "|---|---|---|---|---|---|---|---|"]
        for k, s in S.items():
            x, y = max(s["latency_p50"], 1), s["harm_rate"]
            fs = s["fallback_success"]
            md.append(f"| {s['name']} | {s['latency_p50']:.0f} | {s['latency_p95']:.0f} | {y:.3f} | {s.get('corrected_rate', 0):.3f} | "
                      f"{'—' if fs is None else f'{fs:.3f}'} | {s['clean_pass']:.3f} | {s['cost_per_1k']:.2f} |")
            if k not in PLOT:
                continue
            col = "#94a3b8" if k in ("A", "B1", "B2", "E") else ("#16a34a" if k.startswith("T") else
                                                               "#f59e0b" if k in ("C7", "CF") else "#2563eb")
            ax.scatter(x, y, s=40 + 25 * s["cost_per_1k"], color=col, alpha=.8, edgecolor="k", lw=.5)
            ax.annotate(f"{SHORT.get(k, k)} ¥{s['cost_per_1k']:.1f}/千", (x, y), fontsize=8.5, xytext=OFF.get(k, (6, 4)),
                        textcoords="offset points")
            if s.get("corrected_rate"):
                ax.scatter(x, y + s["corrected_rate"], marker="_", color=col, s=80)
                ax.plot([x, x], [y, y + s["corrected_rate"]], color=col, lw=.8, ls=":")
        ax.set_xscale("log")
        ax.set_xlabel("用户感知时延 P50（ms，对数）")
        ax.set_ylabel("用户受损率")
        ax.set_title(title, fontsize=11)
        ax.grid(alpha=.3)
    fig.suptitle("点越靠左下越好；点大小 ∝ 每千条成本；虚线向上 = 先展示后更正的占比", fontsize=10)
    fig.tight_layout()
    (ROOT / "docs").mkdir(exist_ok=True)
    fig.savefig(ROOT / "docs" / "tradeoff.png", dpi=150)
    (ROOT / "eval" / "tradeoff.md").write_text("\n".join(md), encoding="utf-8")
    print("wrote docs/tradeoff.png eval/tradeoff.md")


if __name__ == "__main__":
    sys.exit(main())
