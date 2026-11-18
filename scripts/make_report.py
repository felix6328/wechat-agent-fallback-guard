"""从 eval/traces.jsonl 生成静态演示页 app/report.html（不调 API）：
同一条指令，四种 Agent（无检测 / 仅规则·严格 / 规则+LLM 同步 / 分层+缓存）的处置轨迹并排对比（种子 42）。"""
import html
import json
import sys
from collections import defaultdict
from pathlib import Path


# v1 轨迹里的旧文案提到「微信支付」，与当前实现（支付宝沙箱，fbagent/agent.py 第 469 行）不一致。
# 轨迹文件保留原样作为历史记录，只在渲染演示页时统一成当前文案。
LEGACY_REPLY = {"结果会通过微信支付通知你": "支付结果会通过支付平台通知你"}
def legacy(text: str) -> str:
    for old, new in LEGACY_REPLY.items():
        text = text.replace(old, new)
    return text

ROOT = Path(__file__).resolve().parent.parent
SHOW_KEYS = ["A", "B2", "H32", "T32C"]
rows = [json.loads(l) for l in open(ROOT / "eval" / "traces.jsonl", encoding="utf-8")]
by = defaultdict(dict)
meta = {}
names = {}
for r in rows:
    if r.get("config_key") in SHOW_KEYS and r["seed"] == 42:
        by[r["id"]][r["config_key"]] = r
        names[r["config_key"]] = r["config"]
        meta[r["id"]] = r
SHOW = SHOW_KEYS
cases = {c["id"]: c for c in json.loads((ROOT / "data" / "testset.json").read_text(encoding="utf-8"))}
color = {"ok": "#16a34a", "degraded": "#ca8a04", "fallback": "#2563eb", "human": "#7c3aed", "failed": "#dc2626"}
e = html.escape
parts = ["""<!doctype html><html lang="zh"><meta charset="utf-8"><title>异常检测兜底 Agent · 轨迹对比</title>
<style>body{font-family:-apple-system,"PingFang SC",sans-serif;margin:24px;background:#f8fafc;color:#0f172a}
h1{font-size:22px}.case{background:#fff;border:1px solid #e2e8f0;border-radius:10px;margin:14px 0;padding:14px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.col{border:1px solid #e2e8f0;border-radius:8px;padding:10px;font-size:13px}
.tag{display:inline-block;color:#fff;border-radius:4px;padding:1px 6px;font-size:12px}.bad{background:#fee2e2}.good{background:#f0fdf4}
code{font-size:12px;color:#334155}.meta{color:#64748b;font-size:13px}select{font-size:14px;padding:4px}</style>
<h1>异常检测兜底 Agent · 同一指令四种处置对比</h1>
<p class="meta">模拟环境、合成数据（不是微信生产系统）。绿底 = 处置正确；红底 = 处置错误（暴露错误数据 / 先展示后更正 / 重复扣款 / 结局不在可接受集合）。时延 = 用户感知时延（分层方案不含异步复核）。数字来自 eval/traces.jsonl。</p>
<p>筛选类别：<select id="f" onchange="for(const d of document.querySelectorAll('.case'))d.style.display=(this.value==''||d.dataset.cat==this.value)?'':'none'">
<option value="">全部</option>"""]
cats = list(dict.fromkeys(c["category"] for c in cases.values()))
parts += [f'<option value="{c}">{c}</option>' for c in cats]
parts.append("</select></p>")
for cid, c in cases.items():
    if cid not in by:
        continue
    parts.append(f'<div class="case" data-cat="{c["category"]}"><b>{cid}</b> {e(c["instruction"])} '
                 f'<span class="meta">类别 {c["category"]}｜注入 {e(json.dumps(c["fault_plan"], ensure_ascii=False)) or "无"}｜可接受 {"/".join(c["acceptable"])}</span>'
                 f'<div class="meta">{e(c.get("why", ""))}</div><div class="grid">')
    for name in SHOW:
        r = by[cid].get(name)
        if not r:
            parts.append('<div class="col">（未运行）</div>')
            continue
        cls = "good" if r["correct"] else "bad"
        acts = "<br>".join(e(x) for x in r["actions"])
        harm = []
        if r["exposure"]:
            harm.append("暴露错误数据")
        if r.get("corrected"):
            harm.append("先展示后【更正】")
        if r["harm"]["duplicate_charge"]:
            harm.append(f"重复扣款（{r['harm']['n_charges']} 次）")
        if r["harm"]["duplicate_order"]:
            harm.append("重复下单")
        parts.append(f'<div class="col {cls}"><b>{e(names.get(name, name))}</b><br><span class="tag" style="background:{color[r["outcome"]]}">{r["outcome"]}</span> '
                     f'{r["latency_ms"]:.0f}ms {"｜⚠ " + "、".join(harm) if harm else ""}<br><code>{acts}</code><br>💬 {e(legacy(r["reply"]))}</div>')
    parts.append("</div></div>")
parts.append("""<script>const h=decodeURIComponent(location.hash.slice(1));if(h){const f=document.getElementById('f');f.value=h;f.onchange();}</script>""")
(ROOT / "app" / "report.html").write_text("\n".join(parts), encoding="utf-8")
print("wrote app/report.html")
