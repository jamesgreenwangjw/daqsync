from __future__ import annotations

import csv
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, ROOT)

from daqsync import FrameTable, MockCamera, MockDetector, MockSerial, Session, parse_kv_line
from daqsync.clocks import fit_linear_clock
from daqsync.table import CSV_FIELDS


class TestParse(unittest.TestCase):
    def test_kv(self):
        d = parse_kv_line("T=1234,ADC=2048")
        self.assertEqual(d["T"], 1234)
        self.assertEqual(d["ADC"], 2048)


class TestClockFit(unittest.TestCase):
    def test_linear(self):
        host = [i * 0.01 for i in range(20)]
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
        # 推理设定 30ms，但 MockDetector 的 sleep 在高负载 runner 上会因
        # 线程调度延迟放大数倍（实测 macOS runner 中位数已达 0.11s），
        # 故只断言推理确实产生了可观测的滞后，不把绝对值作为判据。
        median_lag = sorted(lags)[len(lags) // 2]
        self.assertGreater(median_lag, 0.02)
        self.assertLess(median_lag, 0.5)
        for r in table.rows:
            if r["boxes"]:
                for b in r["boxes"]:
                    self.assertEqual(b["frame_id"], r["frame_id"])
        slags = [r["serial_lag_s"] for r in table.rows if r["serial_lag_s"] is not None]
        self.assertTrue(slags)
        self.assertLess(sum(slags) / len(slags), 0.02)

    def test_slow_detect_does_not_drop_mock_fps(self):
        fps = 30.0
        seconds = 0.8
        s = Session(
            MockCamera(fps=fps),
            MockSerial(interval_s=0.01),
            MockDetector(infer_delay_s=0.05),
        )
        table = s.run(seconds=seconds)
        expected = fps * seconds
        # 推理 50ms 若堵在采集环里，大约只有 16 帧；拆开后应接近 24 帧。
        self.assertGreaterEqual(len(table.rows), int(expected * 0.8))
        self.assertLess(len(table.rows), int(expected) + 8)

        # 采集帧率未被拖垮之外，检测结果也不得随时间堆积：
        # 推理产能（20fps）低于采集（30fps），多余的待检帧应被丢弃，
        # 而不是让 infer_lag_s 持续上升。
        lags = [r["infer_lag_s"] for r in table.rows if r["infer_lag_s"] is not None]
        self.assertTrue(lags)
        # 绝对滞后含推理耗时与调度延迟，随 runner 负载浮动；此处只要求不出现
        # 病态量级。「不随运行时长增长」由 test_session 的无界队列回归用例覆盖。
        self.assertLess(max(lags), 0.5)
        self.assertGreater(table.meta["n_dropped_frames"], 0)
        for r in table.rows:
            if r["boxes"]:
                for b in r["boxes"]:
                    self.assertEqual(b["frame_id"], r["frame_id"])

    def test_csv_flat_and_empty_header(self):
        s = Session(MockCamera(fps=20), MockSerial(), MockDetector(infer_delay_s=0.01))
        table = s.run(seconds=0.35)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "run.csv")
            table.to_csv(path)
            with open(path, newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(list(rows[0].keys()), CSV_FIELDS)
            self.assertTrue(any(r["adc"] for r in rows))
            empty_path = os.path.join(d, "empty.csv")
            FrameTable([], {}).to_csv(empty_path)
            with open(empty_path, newline="") as f:
                header = f.readline().strip().split(",")
            self.assertEqual(header, CSV_FIELDS)
            self.assertGreater(os.path.getsize(empty_path), 0)


if __name__ == "__main__":
    unittest.main()
