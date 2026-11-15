"""第二版新增能力的单元测试（不调用模型）：级联、判定缓存、异步更正、解析兜底、生成集注入、失败即关闭。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import json  # noqa: E402

from fbagent import rules as R  # noqa: E402
from fbagent.evaluate import run_case  # noqa: E402
from fbagent.llm_judge import CascadeJudge, LLMVerdict, VerdictCache  # noqa: E402
from fbagent.llm_parser import LLMParser, validate  # noqa: E402
from fbagent.mock_apis import Env  # noqa: E402

CASES = {c["id"]: c for c in json.loads((ROOT / "data" / "testset.json").read_text(encoding="utf-8"))}


class FakeJudge:
    def __init__(self, anomalous, conf=0.95, ms=1000.0, cost=0.002, name="fake"):
        self.anomalous, self.conf, self.ms, self.cost, self.model = anomalous, conf, ms, cost, name
        self.available, self.n = True, 0

    def judge(self, instruction, op, args, data, soft_flags):
        self.n += 1
        return LLMVerdict(self.anomalous, "semantic_wrong" if self.anomalous else "none", self.conf,
                          "fake", 100, 10, self.ms, False, self.cost, self.model)


class TestCascade(unittest.TestCase):
    def test_confident_normal_not_escalated(self):
        small, big = FakeJudge(False, 0.95), FakeJudge(True)
        v = CascadeJudge(small, big, tau=0.9).judge("i", "weather.query", {}, {}, [])
        self.assertFalse(v.anomalous)
        self.assertEqual(big.n, 0)

    def test_anomalous_or_unsure_escalates_and_sums_latency(self):
        for small in (FakeJudge(True, 0.95, ms=500), FakeJudge(False, 0.5, ms=500)):
            big = FakeJudge(False, 0.99, ms=3000)
            v = CascadeJudge(small, big, tau=0.9).judge("i", "weather.query", {}, {}, [])
            self.assertEqual(big.n, 1)
            self.assertFalse(v.anomalous)          # 大判官终审
            self.assertTrue(v.escalated)
            self.assertAlmostEqual(v.latency_ms, 3500)
            self.assertAlmostEqual(v.cost_cny, 0.004)


class TestVerdictCache(unittest.TestCase):
    def test_same_hour_hits_different_data_misses(self):
        c = VerdictCache()
        d1 = {"city": "北京", "temp_high_c": 9, "updated_at": "2026-11-15T11:23+08:00"}
        d2 = dict(d1, updated_at="2026-11-15T11:48+08:00")
        d3 = dict(d1, temp_high_c=48)
        c.put(c.key("weather.query", {"city": "北京"}, d1, []), "v")
        self.assertEqual(c.get(c.key("weather.query", {"city": "北京"}, d2, [])), "v")
        self.assertIsNone(c.get(c.key("weather.query", {"city": "北京"}, d3, [])))
        self.assertEqual((c.hits, c.misses), (1, 1))


class TestAsyncDisplay(unittest.TestCase):
    def test_async_shows_then_corrects_sync_blocks(self):
        case = CASES["L01"]
        sync = run_case(case, "hybrid", FakeJudge(True), "v1", seed=42)
        asyn = run_case(case, "hybrid", FakeJudge(True), "v1", seed=42, async_display=True)
        self.assertFalse(sync["exposure"])
        self.assertFalse(sync["corrected"])
        self.assertTrue(asyn["corrected"])             # 先展示、后发【更正】
        self.assertFalse(asyn["correct"])              # 更正不算「兜底成功」
        self.assertLess(asyn["latency_ms"], sync["latency_ms"])   # 首答不等 LLM

    def test_writes_stay_sync_under_async_mode(self):
        case = next(c for c in CASES.values() if "timeout_after_charge" in json.dumps(c.get("fault_plan", {})))
        r = run_case(case, "hybrid", FakeJudge(False), "v1", seed=42, async_display=True)
        self.assertFalse(r["harmful"])


class TestParser(unittest.TestCase):
    def test_validate_rejects_out_of_vocab(self):
        self.assertIsNone(validate({"intent": "weather", "city": "火星"}))
        self.assertEqual(validate({"intent": "weather", "city": "上海", "date": "明天"})["city"], "上海")

    def test_no_key_falls_back_to_wordlist(self):
        p = LLMParser(use_cache=False)
        p.key = None
        plan, src, ms, cost = p.parse("北京今天天气怎么样")
        self.assertEqual(src, "fallback")
        self.assertEqual(plan["city"], "北京")
        self.assertEqual(cost, 0.0)


class TestGenOverrideAndFailClosed(unittest.TestCase):
    def test_dict_spec_replaces_body(self):
        bad = {"city": "北京", "date": "2026-11-15", "condition": "晴", "temp_high_c": 48, "temp_low_c": 30,
               "precip_mm": None, "updated_at": "2026-11-15T11:23+08:00", "source": "x"}
        env = Env("t", {"weather.query": [{"kind": "gen_wrong", "data": bad}]}, seed=1)
        r = env.call("weather.query", {"city": "北京", "date": "2026-11-15"})
        self.assertEqual(r.data["temp_high_c"], 48)
        self.assertEqual(env.gt[r.call_id], "gen_wrong")
        v = R.check(r, {"city": "北京", "date": "2026-11-15"})   # precip=None 会让比较抛异常 → 失败即关闭
        self.assertTrue(any(f.type == "schema_error" for f in v.hard))

    def test_gen_clean_has_no_ground_truth_fault(self):
        env = Env("t", {"map.route": [{"kind": "gen_clean", "data": {"x": 1}}]}, seed=1)
        r = env.call("map.route", {"origin": "家", "dest": "公司", "mode": "drive"})
        self.assertIsNone(env.gt[r.call_id])


if __name__ == "__main__":
    unittest.main()
