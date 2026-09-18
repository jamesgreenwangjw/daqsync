from __future__ import annotations

import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, ROOT)

from daqsync import MockCamera, MockDetector, MockSerial, Session, parse_kv_line
from daqsync.clocks import fit_linear_clock


class TestParse(unittest.TestCase):
    def test_kv(self):
        d = parse_kv_line("T=1234,ADC=2048")
        self.assertEqual(d["T"], 1234)
        self.assertEqual(d["ADC"], 2048)


class TestClockFit(unittest.TestCase):
    def test_linear(self):
        host = [i * 0.01 for i in range(20)]
        # MCU 比 host 快 50ppm，且有 1000ms 偏置
        tick = [1000 + h * 1000 * (1 + 50e-6) for h in host]
        ab = fit_linear_clock(host, tick)
        self.assertIsNotNone(ab)
        a, b = ab
        self.assertAlmostEqual(a, 1000 * (1 + 50e-6), delta=0.01)
        self.assertAlmostEqual(b, 1000, delta=0.5)


class TestAlignFrameIdNotInferTime(unittest.TestCase):
    def test_boxes_bind_to_capture_not_infer_end(self):
        cam = MockCamera(fps=25, size=(32, 32))
        ser = MockSerial(interval_s=0.008, drift_ppm=80)
        det = MockDetector(infer_delay_s=0.03)
        s = Session(cam, ser, det)
        table = s.run(seconds=0.6)
        self.assertGreater(len(table.rows), 5)
        lags = [r["infer_lag_s"] for r in table.rows if r["infer_lag_s"] is not None]
        self.assertTrue(lags)
        mean_lag = sum(lags) / len(lags)
        # 推理故意睡了 30ms，如果错误地用 infer_end 当 capture，对齐会漂一帧以上
        self.assertGreater(mean_lag, 0.02)
        self.assertLess(mean_lag, 0.08)
        for r in table.rows:
            if r["boxes"]:
                for b in r["boxes"]:
                    self.assertEqual(b["frame_id"], r["frame_id"])
        slags = [r["serial_lag_s"] for r in table.rows if r["serial_lag_s"] is not None]
        self.assertTrue(slags)
        self.assertLess(sum(slags) / len(slags), 0.02)

    def test_csv_roundtrip(self):
        s = Session(MockCamera(fps=20), MockSerial(), MockDetector(infer_delay_s=0.01))
        table = s.run(seconds=0.35)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "run.csv")
            table.to_csv(path)
            self.assertTrue(os.path.getsize(path) > 20)


if __name__ == "__main__":
    unittest.main()
