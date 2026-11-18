"""评测公共函数：跑一条指令并打分；汇总；bootstrap 置信区间。"""
from __future__ import annotations

import random
import statistics
from typing import Optional

from .agent import Agent
from .mock_apis import Env, WRONG_DATA_KINDS, DISCLOSABLE_KINDS, TRANSPORT_KINDS


def run_case(case: dict, variant: str, judge=None, rules_version="v1", seed=42, random_faults=None,
             async_display=False, verdict_cache=None, llm_parser=None, env=None) -> dict:
    if env is None:
        env = Env(case["id"], case.get("fault_plan", {}), seed=seed, random_faults=random_faults)
    agent = Agent(variant, judge, rules_version, async_display=async_display, verdict_cache=verdict_cache,
                  llm_parser=llm_parser)
    res = agent.run(case["instruction"], env, case["id"], input_plan=case.get("input_plan"))
    calls = []
    for a in res.assessments:
        r = env.calls[a.call_id]
        gt = env.gt[a.call_id]
        content_gt = gt if (gt and gt not in TRANSPORT_KINDS) else None
        calls.append({"call_id": a.call_id, "op": a.op, "status": r.status, "gt_fault": gt,
                      "content_call": r.status == "ok", "gt_content_anomaly": content_gt is not None,
                      "pred": a.anomalous, "pred_type": a.type, "source": a.source, "evidence": a.evidence,
                      "llm_called": a.llm_called, "llm_failed": a.llm_failed, "llm_ms": a.llm_ms,
                      "is_async": a.is_async, "cache_hit": a.cache_hit, "escalated": a.escalated,
                      "prompt_tokens": a.prompt_tokens, "completion_tokens": a.completion_tokens,
                      "cost_cny": a.cost_cny})
    exposure, corrected = [], []
    for cid, caveat in res.shown:
        g = env.gt.get(cid)
        bad = g in WRONG_DATA_KINDS or (g in DISCLOSABLE_KINDS and not caveat)
        if bad and cid in res.corrected:
            corrected.append({"call_id": cid, "fault": g})
        elif bad:
            exposure.append({"call_id": cid, "fault": g, "caveat": caveat})
    # 同一 call 可能先无提示展示、更正后又带提示展示：只要被更正，就算「短暂暴露后更正」
    exposure = [e for e in exposure if e["call_id"] not in {c["call_id"] for c in corrected}]
    harm = env.harm()
    harmful = harm["duplicate_charge"] or harm["duplicate_order"]
    injected = sorted({g if isinstance(g, str) else str(g) for g in env.gt.values() if g})
    acceptable = case.get("acceptable")
    correct = None
    if acceptable is not None:
        correct = (res.outcome in acceptable) and not exposure and not harmful and not corrected
    sync_llm = sum(c["llm_ms"] for c in calls if not c["is_async"])
    async_llm = sum(c["llm_ms"] for c in calls if c["is_async"])
    cost = sum(c["cost_cny"] for c in calls) + res.parse_cost
    return {"id": case["id"], "category": case.get("category"), "instruction": case["instruction"],
            "variant": variant, "seed": seed, "rules_version": rules_version,
            "plan": res.plan, "gold_plan": case.get("gold_plan"), "parse_source": res.parse_source,
            "parse_ms": res.parse_ms,
            "outcome": res.outcome, "acceptable": acceptable, "correct": correct,
            "reply": res.reply, "actions": res.actions, "calls": calls, "exposure": exposure,
            "corrected": corrected, "harm": harm,
            "harmful": harmful, "injected": injected, "gt_anomalous": case.get("gt_anomalous", bool(injected)),
            # 用户感知时延：解析 + 服务 + 退避 + 同步 LLM（异步复核不计入首答时延）
            "latency_ms": res.parse_ms + env.virtual_ms + res.backoff_ms + sync_llm,
            "service_ms": env.virtual_ms, "backoff_ms": res.backoff_ms, "llm_ms": sync_llm, "async_llm_ms": async_llm,
            "llm_calls": sum(c["llm_called"] for c in calls), "cache_hits": sum(c["cache_hit"] for c in calls),
            "escalations": sum(c["escalated"] for c in calls),
            "llm_failed": sum(c["llm_failed"] for c in calls),
            "prompt_tokens": sum(c["prompt_tokens"] for c in calls),
            "completion_tokens": sum(c["completion_tokens"] for c in calls), "cost_cny": cost}


def pct(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def prf(rows, content_only=True):
    tp = fp = fn = tn = 0
    for r in rows:
        for c in r["calls"]:
            if content_only and not c["content_call"]:
                continue
            g = c["gt_content_anomaly"] if content_only else bool(c["gt_fault"])
            p = c["pred"]
            tp += g and p
            fp += (not g) and p
            fn += g and (not p)
            tn += (not g) and (not p)
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else 0.0
    fpr = fp / (fp + tn) if fp + tn else None
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": prec, "recall": rec, "f1": f1, "fpr": fpr}


def point_metrics(rows) -> dict:
    anom = [r for r in rows if r["gt_anomalous"]]
    clean = [r for r in rows if not r["gt_anomalous"]]
    c = prf(rows, True)
    n = len(rows)
    lat = [r["latency_ms"] for r in rows]
    return {
        "recall": c["recall"], "precision": c["precision"], "f1": c["f1"], "fpr": c["fpr"],
        "fallback_success": sum(r["correct"] for r in anom) / len(anom) if anom else None,
        "clean_pass": sum(r["correct"] for r in clean) / len(clean) if clean else None,
        "task_success": sum(r["correct"] for r in rows) / n if rows and rows[0]["correct"] is not None else None,
        "harm_rate": sum(bool(r["exposure"]) or r["harmful"] for r in rows) / n,
        "corrected_rate": sum(bool(r["corrected"]) for r in rows) / n,
        "latency_p50": pct(lat, 50), "latency_p95": pct(lat, 95),
        "cost_per_1k": 1000 * sum(r["cost_cny"] for r in rows) / n,
        "llm_calls_per_case": sum(r["llm_calls"] for r in rows) / n,
    }


def bootstrap_ci(rows, metric_keys, n_boot=1000, seed=0):
    """按「指令」整簇重抽样（同一指令的多个种子一起抽），给出 95% 区间。"""
    by = {}
    for r in rows:
        by.setdefault(r["id"], []).append(r)
    ids = list(by)
    rng = random.Random(seed)
    samples = {k: [] for k in metric_keys}
    for _ in range(n_boot):
        pick = [x for _ in ids for x in by[rng.choice(ids)]]
        m = point_metrics(pick)
        for k in metric_keys:
            if m[k] is not None:
                samples[k].append(m[k])
    return {k: (pct(v, 2.5), pct(v, 97.5)) if v else (None, None) for k, v in samples.items()}


def summarize(rows):
    m = point_metrics(rows)
    c = prf(rows, True)
    seeds = sorted({r["seed"] for r in rows})
    per_seed = {s: point_metrics([r for r in rows if r["seed"] == s]) for s in seeds}
    keys = ["recall", "precision", "fpr", "fallback_success", "clean_pass", "harm_rate", "latency_p50", "cost_per_1k"]
    ci = bootstrap_ci(rows, keys)
    std = {}
    for k in keys:
        vals = [v[k] for v in per_seed.values() if v[k] is not None]
        std[k] = statistics.pstdev(vals) if len(vals) > 1 else (0.0 if vals else None)
    return {**m, "confusion": c, "ci95": ci, "seed_std": std, "seeds": seeds, "n_rows": len(rows),
            "n_cases": len({r["id"] for r in rows}),
            "harm_cases": sum(bool(r["exposure"]) or r["harmful"] for r in rows),
            "dup_charge": sum(r["harm"]["duplicate_charge"] for r in rows),
            "dup_order": sum(r["harm"]["duplicate_order"] for r in rows),
            "cache_hits": sum(r["cache_hits"] for r in rows), "escalations": sum(r["escalations"] for r in rows),
            "llm_calls": sum(r["llm_calls"] for r in rows), "llm_failed": sum(r["llm_failed"] for r in rows),
            "cost_total": sum(r["cost_cny"] for r in rows),
            "outcomes": {k: sum(r["outcome"] == k for r in rows) for k in ("ok", "degraded", "fallback", "human", "failed")}}
