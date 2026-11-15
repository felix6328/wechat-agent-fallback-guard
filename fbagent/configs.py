"""评测用的配置注册表：变体 × 判官 × 时延策略。"""
from __future__ import annotations

from .llm_judge import CascadeJudge, LLMJudge, VerdictCache

M7 = "Qwen/Qwen2.5-7B-Instruct"
MV4F = "deepseek-ai/DeepSeek-V4-Flash"
MV32 = "deepseek-ai/DeepSeek-V3.2"

_J = {}


def judge(name: str):
    """7b / v4f / v32 / v32p1 / 7b>v32 / v4f>v32"""
    if name in _J:
        return _J[name]
    if name == "7b":
        j = LLMJudge(M7, prompt_version="v2")
    elif name == "v4f":
        j = LLMJudge(MV4F, prompt_version="v2")
    elif name == "v32":
        j = LLMJudge(MV32, prompt_version="v2")
    elif name == "v32p1":
        j = LLMJudge(MV32, prompt_version="v1")
    elif name == "7b>v32":
        j = CascadeJudge(judge("7b"), judge("v32"), tau=0.0)
    elif name == "v4f>v32":
        j = CascadeJudge(judge("v4f"), judge("v32"), tau=0.9)
    else:
        raise KeyError(name)
    _J[name] = j
    return j


# (key, 展示名, variant, judge, rules_version, async_display, verdict_cache)
CONFIGS = [
    ("A", "A 无检测（SDK 式盲重试）", "naive", None, "v1", False, False),
    ("B1", "B1 仅规则·宽松", "rules_lenient", None, "v1", False, False),
    ("B2", "B2 仅规则·严格", "rules_strict", None, "v1", False, False),
    ("E", "E 严格规则 + v2 蒸馏规则", "rules_strict", None, "v2", False, False),
    ("H7", "H-7B 规则 + Qwen2.5-7B（免费）", "hybrid", "7b", "v1", False, False),
    ("HF", "H-V4F 规则 + DeepSeek-V4-Flash", "hybrid", "v4f", "v1", False, False),
    ("H32", "H-V3.2 规则 + DeepSeek-V3.2", "hybrid", "v32", "v1", False, False),
    ("DF", "D-V4F 纯 LLM 质检（V4-Flash）", "llm_only", "v4f", "v1", False, False),
    ("C7", "CAS 级联 7B→V3.2（7B 判异常才升级）", "hybrid", "7b>v32", "v1", False, False),
    ("CF", "CAS 级联 V4F→V3.2（异常或置信<0.9 升级）", "hybrid", "v4f>v32", "v1", False, False),
    ("TF", "T 分层：决策/写同步 + 展示异步（V4F）", "hybrid", "v4f", "v1", True, False),
    ("TFC", "T+C 分层 + 判定缓存（V4F）", "hybrid", "v4f", "v1", True, True),
    ("T32", "T 分层：决策/写同步 + 展示异步（V3.2）", "hybrid", "v32", "v1", True, False),
    ("T32C", "T+C 分层 + 判定缓存（V3.2）", "hybrid", "v32", "v1", True, True),
]
BY_KEY = {c[0]: c for c in CONFIGS}


def new_cache(cfg):
    return VerdictCache() if cfg[6] else None
