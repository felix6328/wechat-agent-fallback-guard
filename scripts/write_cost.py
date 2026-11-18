"""从 data/cost/llm.jsonl（不入库、不含密钥）汇总生成 docs/COST.md。不调 API。"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fbagent.llm_judge import PRICES, cost_cny  # noqa: E402

agg = defaultdict(lambda: [0, 0, 0, []])
for line in open(ROOT / "data" / "cost" / "llm.jsonl", encoding="utf-8"):
    r = json.loads(line)
    pur = r.get("purpose", "judge")
    k = (r["model"], pur if pur != "judge" else "质检 prompt " + r.get("prompt_version", "v1（早期日志未记版本）"))
    a = agg[k]
    a[0] += 1
    a[1] += r["prompt_tokens"]
    a[2] += r["completion_tokens"]
    a[3].append(r["latency_ms"])
L = ["# 费用口径（自动生成：python scripts/write_cost.py）\n",
     "来源：[硅基流动价格页](https://www.siliconflow.cn/pricing)，查阅 2026-11-15（Asia/Shanghai）。"
     "**按接口返回的 token × 官网标价估算，不是账单原件**；价格会变。原始日志 `data/cost/llm.jsonl` 已在 .gitignore，含模型、token、时延、请求哈希，不含密钥。\n",
     "磁盘缓存命中的重跑不计费、不进日志。所以下表是本项目开发至今**全部有日志的计费请求**（含冒烟测试、三套测试集 × 多种子、随机压测、解析基准、独立测试集生成）。另有约 16 次模型选型时的时延探测请求没有写日志，按 token 估算约 ¥0.03，未计入下表。\n",
     "## 标价（元 / 百万 token）\n", "| 模型 | 输入 | 输出 | 备注 |\n|---|---|---|---|"]
for m, p in PRICES.items():
    L.append(f"| `{m}` | {p['in']} | {p['out']} | {p['note']} |")
L.append("\n## 合计（按模型 × 用途）\n\n| 模型 | 用途 | 计费请求 | prompt token | completion token | 估算 ¥ | 单次时延 P50 ms |\n|---|---|---|---|---|---|---|")
tot = [0, 0, 0, 0.0]
for (m, pv), (n, pt, ct, lat) in sorted(agg.items()):
    c = cost_cny(m, pt, ct)
    lat.sort()
    L.append(f"| `{m}` | {pv} | {n} | {pt} | {ct} | {c:.4f} | {lat[len(lat) // 2]:.0f} |")
    tot = [tot[0] + n, tot[1] + pt, tot[2] + ct, tot[3] + c]
L.append(f"| **合计** | | **{tot[0]}** | **{tot[1]}** | **{tot[2]}** | **{tot[3]:.4f}** | |")
L.append(f"\n两轮开发的预算上限合计约 ¥11（第一轮 ¥5 + 第二轮 ¥6），有日志的实际估算 ¥{tot[3]:.2f}。代码里有花费护栏：`FB_SPEND_CAP_CNY`，每次请求前读日志累计，超过即抛异常。\n")
st = json.loads((ROOT / "eval" / "stress_results.json").read_text(encoding="utf-8"))["variants"]
L.append("## 换算成线上口径（假设，需线上数据校准）\n")
L.append("随机压测（300 会话，接近「大部分请求正常」的流量形态）里每会话的模型费用：\n")
L.append("| 配置 | ¥ / 千会话 | 判定缓存命中 |\n|---|---|---|")
for k, v in st.items():
    if v["cost_total"]:
        L.append(f"| {k} | {1000 * v['cost_total'] / v['episodes']:.2f} | {v.get('cache_hits', 0)} / {v['llm_calls']} |")
L.append("\n- 按每天 100 万次 Agent 会话（**假设值**，不是微信数据）：同步混合方案约 ¥2,500–3,000 / 天；分层 + 判定缓存约 ¥1,100–1,300 / 天。")
L.append("- 这是公网 API 标价。平台自研模型内部部署、蒸馏成专用小模型后，边际成本会再降一个量级以上（推断，未测）。")
L.append("- 真正的约束仍是时延：见 docs/DESIGN.md §11。")
(ROOT / "docs/COST.md").write_text("\n".join(L), encoding="utf-8")
print("\n".join(L[-12:]))
