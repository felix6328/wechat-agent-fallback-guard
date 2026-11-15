"""命令行演示：一条指令 + 自定义故障，看 Agent 怎么处置。

例：
  python scripts/demo.py "在沙县小吃点一份鸡腿饭并付款" --fault pay.create=timeout_after_charge --variant naive
  python scripts/demo.py "在沙县小吃点一份鸡腿饭并付款" --fault pay.create=timeout_after_charge --variant rules_strict
  FB_ENV_FILE=... python scripts/demo.py "广州后天天气" --fault weather.query=sem_condition_season --variant hybrid
  FB_ENV_FILE=... python scripts/demo.py "广州后天天气" --fault weather.query=sem_condition_season --variant hybrid --async-display
  FB_ENV_FILE=... python scripts/demo.py "魔都明儿下雨不" --llm-parser
故障名见 fbagent/mock_apis.py；多个故障用逗号分隔表示第 1/2/3 次调用，如 weather.query=timeout,timeout,ok
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fbagent.evaluate import run_case  # noqa: E402
from fbagent.llm_judge import LLMJudge  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("instruction")
ap.add_argument("--fault", action="append", default=[])
ap.add_argument("--variant", default="rules_strict", choices=["naive", "rules_lenient", "rules_strict", "hybrid", "llm_only"])
ap.add_argument("--model", default="deepseek-ai/DeepSeek-V3.2")
ap.add_argument("--prompt", default="v2")
ap.add_argument("--async-display", action="store_true", help="分层：纯展示的读先展示、后台复核、错了发【更正】")
ap.add_argument("--llm-parser", action="store_true", help="用 LLM function calling 解析指令（失败回退词表）")
a = ap.parse_args()
plan = {}
for f in a.fault:
    op, _, kinds = f.partition("=")
    plan[op] = kinds.split(",")
judge = LLMJudge(a.model, prompt_version=a.prompt) if a.variant in ("hybrid", "llm_only") else None
if judge and not judge.available:
    sys.exit("未找到 SILICONFLOW_API_KEY（见 .env.example）")
parser = None
if a.llm_parser:
    from fbagent.llm_parser import LLMParser  # noqa: E402
    parser = LLMParser()
r = run_case({"id": "demo", "instruction": a.instruction, "fault_plan": plan}, a.variant, judge,
             async_display=a.async_display, llm_parser=parser)
print("解析:", json.dumps(r["plan"], ensure_ascii=False), f"（{r.get('parse_source', 'wordlist')}）")
print("轨迹:")
for x in r["actions"]:
    print("  ", x)
print("回复:", r["reply"])
print(f"结局: {r['outcome']}  用户感知 {r['latency_ms']:.0f}ms（服务 {r['service_ms']:.0f} + 退避 {r['backoff_ms']:.0f} + 同步 LLM {r['llm_ms']:.0f}；后台复核 {r['async_llm_ms']:.0f}）"
      + ("  ⚠ 先展示后更正" if r["corrected"] else ""))
print("错误数据暴露:", r["exposure"] or "无", " 扣款次数:", r["harm"]["n_charges"], " 下单次数:", r["harm"]["n_orders"])
