"""Offline tests for the read-only performance lab."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).with_name("ps4_perf_lab.py")
spec = importlib.util.spec_from_file_location("ps4_perf_lab", MODULE)
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


def make_log(speeds, ee=27.1, gs=22.2, vu=21.8):
    return "\n".join(
        f"[PS4] Performance: seconds={i * 5:.1f} PS2_Hz={speed * 0.6:.2f} "
        f"Speed_pct={speed:.2f} Game_FPS={speed * 0.6:.2f} "
        f"EE_ms={ee:.2f} GS_ms={gs:.2f} VU1_ms={vu:.2f} GPU_ms=2.3"
        for i, speed in enumerate(speeds)
    )


class PerformanceTests(unittest.TestCase):
    def test_warmup_filters_early_data(self):
        samples = lab.parse_samples(make_log([20, 30, 60, 64, 65]), warmup=10)
        self.assertEqual(len(samples), 3)
        self.assertEqual(samples[0]["Speed_pct"], 60)

    def test_dominant_ee_and_budget(self):
        samples = lab.parse_samples(make_log([64] * 16), warmup=0)
        out = lab.summarize(samples)
        self.assertEqual(out["dominant_component_by_median"], "EE_ms")
        self.assertEqual(out["over_budget_components"], ["EE_ms", "GS_ms", "VU1_ms"])
        self.assertEqual(out["metrics"]["Speed_pct"]["median"], 64)

    def test_invalid_samples_are_ignored(self):
        samples = lab.parse_samples("Performance: seconds=10 Speed_pct=NaN\n"
                                    "Performance: seconds=10 Speed_pct=50 EE_ms=20\n"
                                    "Performance: seconds=12 Speed_pct=55\n", warmup=0)
        self.assertEqual(len(samples), 2)

    def test_no_samples_rejected(self):
        with self.assertRaisesRegex(ValueError, "nenhuma linha"):
            lab.summarize([])

    def test_compare_includes_positive_speed_delta(self):
        with tempfile.TemporaryDirectory() as folder:
            a = Path(folder) / "before.log"
            b = Path(folder) / "after.log"
            a.write_text(make_log([64] * 12), encoding="utf-8")
            b.write_text(make_log([70] * 12), encoding="utf-8")
            old = lab.load_summary(a, 30)
            new = lab.load_summary(b, 30)
            self.assertEqual(new["metrics"]["Speed_pct"]["median"] - old["metrics"]["Speed_pct"]["median"], 6)


if __name__ == "__main__":
    unittest.main()
