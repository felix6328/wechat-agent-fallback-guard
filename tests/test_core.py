"""单元测试（不调用模型）：python -m unittest discover -s tests -v"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fbagent import envload  # noqa: E402
from fbagent.agent import Agent  # noqa: E402
from fbagent.evaluate import run_case  # noqa: E402
from fbagent.mock_apis import Env  # noqa: E402
from fbagent import rules as R  # noqa: E402

CASES = {c["id"]: c for c in json.loads((ROOT / "data" / "testset.json").read_text(encoding="utf-8"))}


class StubJudge:
    """模拟 LLM 不可用：永远返回 None。"""
    model = "stub"

    def judge(self, *a, **k):
        return None


class TestEnvLoad(unittest.TestCase):
    def test_only_reads_siliconflow_key(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
            f.write("DATABASE_URL=postgres://secret\nJWT_SECRET=abc\nexport SILICONFLOW_API_KEY='dummy-test-key'\n")
        import os
        os.environ["FB_ENV_FILE"] = f.name
        self.assertEqual(envload.load_siliconflow_api_key(), "dummy-test-key")
        self.assertNotIn("DATABASE_URL", os.environ)
        self.assertNotIn("JWT_SECRET", os.environ)


class TestFaults(unittest.TestCase):
    def test_only_three_services_faultable(self):
        with self.assertRaises(ValueError):
            Env("x", {"ride.estimate": ["timeout"]})

    def test_seeded_reproducible(self):
        a = run_case(CASES["R01"], "naive", None)
        b = run_case(CASES["R01"], "naive", None)
        self.assertEqual(a["reply"], b["reply"])


class TestRules(unittest.TestCase):
    def _r(self, case_id):
        env = Env(case_id, CASES[case_id]["fault_plan"])
        return env

    def test_schema_missing_is_hard(self):
        env = Env("S01", {"weather.query": ["schema_missing"]})
        r = env.call("weather.query", {"city": "上海", "date": "2026-11-15"})
        v = R.check(r, {"city": "上海", "date": "2026-11-15"})
        self.assertTrue(any(f.type == "schema_error" for f in v.hard))

    def test_80c_hard_and_minus32_soft(self):
        env = Env("R01", {"weather.query": ["sem_range_temp"]})
        r = env.call("weather.query", {"city": "广州", "date": "2026-11-16"})
        self.assertTrue(R.check(r, {}).hard)
        env2 = Env("H01")
        r2 = env2.call("weather.query", {"city": "漠河", "date": "2026-11-16"})
        v2 = R.check(r2, {"city": "漠河", "date": "2026-11-16"})
        self.assertFalse(v2.hard)
        self.assertTrue(v2.soft)


class TestPaymentSafety(unittest.TestCase):
    def test_naive_double_charges_on_timeout_after_charge(self):
        r = run_case(CASES["PAY01"], "naive", None)
        self.assertTrue(r["harm"]["duplicate_charge"])

    def test_policy_never_double_charges(self):
        for cid in ("PAY01", "PAY02", "PAY03", "PAY05", "PAY06", "PAY07", "PAY08"):
            for v in ("rules_lenient", "rules_strict"):
                r = run_case(CASES[cid], v, None)
                self.assertFalse(r["harm"]["duplicate_charge"], (cid, v))
                self.assertFalse(r["harm"]["duplicate_order"], (cid, v))

    def test_processing_goes_to_human(self):
        r = run_case(CASES["PAY05"], "rules_lenient", None)
        self.assertEqual(r["outcome"], "human")
        self.assertEqual(r["harm"]["n_charges"], 1)

    def test_amount_mismatch_goes_to_human(self):
        r = run_case(CASES["PAY04"], "rules_lenient", None)
        self.assertEqual(r["outcome"], "human")


class TestLLMFailure(unittest.TestCase):
    def test_llm_down_falls_back_to_strict_on_soft(self):
        r = run_case(CASES["H01"], "hybrid", StubJudge())
        # LLM 挂了 → soft 可疑项按保守规则处理（误兜底，但不暴露错误数据）
        self.assertEqual(r["outcome"], "fallback")
        self.assertGreater(r["llm_failed"], 0)

    def test_llm_down_clean_passes(self):
        r = run_case(CASES["C01"], "hybrid", StubJudge())
        self.assertEqual(r["outcome"], "ok")


if __name__ == "__main__":
    unittest.main()
