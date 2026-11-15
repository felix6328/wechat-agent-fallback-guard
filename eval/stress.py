"""随机故障压测：按 configs/faults.json 的单次调用故障率（默认 10%，假设值）随机注入，
看「用户最终受损率」在各变体下是多少。用于把「接口异常率」翻译成「用户体验」。

- 指令池：主测试集 + 留出集里未注入故障的指令（clean + hard_negative，共 26 条）
- 每个 episode 用不同种子；故障在 food / weather / pay 的每次调用上独立抽样
- 没有逐条人工标注的可接受结局，所以这里只报客观结果：错误数据暴露、重复扣款/下单、失败、无故障时的误兜底
用法：FB_ENV_FILE=... python eval/stress.py --n 300
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fbagent.evaluate import run_case, pct  # noqa: E402
from fbagent.configs import BY_KEY, judge as get_judge, new_cache  # noqa: E402
from fbagent.mock_apis import load_fault_config  # noqa: E402

KEYS = ["A", "B1", "B2", "E", "HF", "H32", "CF", "TF", "TFC"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--rate", type=float, default=None)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    cfg = load_fault_config()
    if a.rate is not None:
        cfg["per_call_fault_rate"] = a.rate
    pool = [c for f in ("testset.json", "holdout.json")
            for c in json.loads((ROOT / "data" / f).read_text(encoding="utf-8")) if not c["gt_anomalous"]]
    eps = []
    for i in range(a.n):
        c = dict(pool[i % len(pool)])
        c["id"] = f"S{i:04d}-{c['id']}"
        c["fault_plan"] = {}
        c.pop("acceptable", None)
        c.pop("gt_anomalous", None)
        eps.append(c)
    prev = ROOT / "eval" / "stress_results.json"
    out = {"rate": cfg["per_call_fault_rate"], "n": a.n, "pool": len(pool), "variants": {}}
    for key in (a.only.split(",") if a.only else KEYS):
        cfgk = BY_KEY[key]
        _, name, variant, jname, rv, asyn, _ = cfgk
        if jname and a.no_llm:
            continue
        judge = get_judge(jname) if jname else None
        vc = new_cache(cfgk)
        with ThreadPoolExecutor(max_workers=a.workers if judge else 1) as ex:
            rows = list(ex.map(lambda c: run_case(c, variant, judge, rv, seed=7, random_faults=cfg,
                                                  async_display=asyn, verdict_cache=vc), eps))
        faulty = [r for r in rows if r["injected"]]
        clean = [r for r in rows if not r["injected"]]
        bad = [r for r in rows if r["exposure"] or r["harmful"]]
        s = {
            "episodes": len(rows), "episodes_with_fault": len(faulty),
            "fault_episode_rate": len(faulty) / len(rows),
            "user_harm_rate": len(bad) / len(rows),
            "exposure_rate": sum(bool(r["exposure"]) for r in rows) / len(rows),
            "corrected_rate": sum(bool(r["corrected"]) for r in rows) / len(rows),
            "cache_hits": sum(r["cache_hits"] for r in rows), "key": key,
            "dup_charge": sum(r["harm"]["duplicate_charge"] for r in rows),
            "dup_order": sum(r["harm"]["duplicate_order"] for r in rows),
            "failed_rate": sum(r["outcome"] == "failed" for r in rows) / len(rows),
            "over_fallback_on_clean": sum(r["outcome"] != "ok" for r in clean) / len(clean) if clean else None,
            "outcomes": {k: sum(r["outcome"] == k for r in rows) for k in ("ok", "degraded", "fallback", "human", "failed")},
            "latency_p50": pct([r["latency_ms"] for r in rows], 50), "latency_p95": pct([r["latency_ms"] for r in rows], 95),
            "cost_total": sum(r["cost_cny"] for r in rows), "llm_calls": sum(r["llm_calls"] for r in rows),
            "llm_failed": sum(r["llm_failed"] for r in rows),
        }
        out["variants"][name] = s
        print(name, json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}, ensure_ascii=False))
    if a.only and prev.exists():   # 增量跑：合并已有结果
        old = json.loads(prev.read_text(encoding="utf-8"))
        old["variants"].update(out["variants"])
        out = {**old, "variants": old["variants"]}
    out["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S %z")
    (ROOT / "eval" / "stress_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
