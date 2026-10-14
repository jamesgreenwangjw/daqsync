from __future__ import annotations

import os
import queue as queue_mod
import statistics
import sys
import threading
import time
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, ROOT)

from daqsync import MockCamera, MockDetector, MockSerial, Session
from daqsync.session import _enqueue_latest
from daqsync.streams.base import Stream


class BlockingCamera(Stream):
    """poll() 阻塞到下一帧，模拟真实 Camera。

    MockCamera 是非阻塞的，因此基于 Mock 的测试无法复现「串口时间戳被
    相机帧周期量化」这一缺陷，必须用阻塞替身。
    """

    def __init__(self, fps: float = 30.0, name: str = "cam0"):
        self._inner = MockCamera(fps=fps, name=name)
        self._frame_period = 1.0 / fps

    def start(self) -> None:
        self._inner.start()

    def stop(self) -> None:
        self._inner.stop()

    def poll(self):
        time.sleep(self._frame_period)
        return self._inner.poll()


class RecordingSerial(Stream):
    """记录每次 poll() 的时刻，用于检测串口线程是否被相机阻塞饿死。"""

    def __init__(self, interval_s: float = 0.01):
        self._inner = MockSerial(interval_s=interval_s)
        self.poll_times = []

    def start(self) -> None:
        self._inner.start()

    def stop(self) -> None:
        self._inner.stop()

    def poll(self):
        self.poll_times.append(time.perf_counter())
        return self._inner.poll()


class CountingStream(Stream):
    """统计 start()/stop() 调用次数。"""

    def __init__(self, inner: Stream):
        self._inner = inner
        self.n_start = 0
        self.n_stop = 0

    def start(self) -> None:
        self.n_start += 1
        self._inner.start()

    def stop(self) -> None:
        self.n_stop += 1
        self._inner.stop()

    def poll(self):
        return self._inner.poll()


class BoomDetector:
    """detect() 立即抛错，用于验证跨线程异常传播。"""

    def detect(self, frame_sample):
        raise RuntimeError("boom")


class TestEnqueueLatest(unittest.TestCase):
    def test_never_blocks_and_keeps_newest(self):
        q = queue_mod.Queue(maxsize=1)
        for i in range(10):
            _enqueue_latest(q, i)
        self.assertEqual(q.qsize(), 1)
        self.assertEqual(q.get(), 9)

    def test_maxsize_two_keeps_two_newest(self):
        q = queue_mod.Queue(maxsize=2)
        for i in range(10):
            _enqueue_latest(q, i)
        self.assertEqual(q.qsize(), 2)
        self.assertEqual(q.get(), 8)
        self.assertEqual(q.get(), 9)

    def test_reports_drop(self):
        q = queue_mod.Queue(maxsize=1)
        self.assertFalse(_enqueue_latest(q, 0))
        self.assertTrue(_enqueue_latest(q, 1))


class TestInferLagBounded(unittest.TestCase):
    def test_lag_bounded_when_detector_slower_than_camera(self):
        # 采集 30fps，推理 40ms（产能 25fps）：修复前队列无界积压，
        # infer_lag_s 随运行时长线性上升；修复后它是一个不随时间增长的常数。
        s = Session(
            MockCamera(fps=30),
            MockSerial(interval_s=0.01),
            MockDetector(infer_delay_s=0.04),
        )
        table = s.run(seconds=2.0)
        lags = [r["infer_lag_s"] for r in table.rows if r["infer_lag_s"] is not None]
        self.assertTrue(lags)

        # 该常数的绝对值 = 推理耗时 + 调度延迟，后者在高负载 runner 上会
        # 被放大数倍，故只要求不出现病态量级：修复前 2 秒内该值升至 0.9 左右。
        self.assertLess(max(lags), 0.5)

        # 核心判据：不随运行时长增长。修复前后半段均值远高于前半段。
        half = len(lags) // 2
        self.assertGreater(half, 2)
        first = statistics.mean(lags[:half])
        second = statistics.mean(lags[half:])
        self.assertLess(second, first * 1.5 + 0.05)

    def test_capture_rate_not_dragged_down(self):
        s = Session(
            MockCamera(fps=30),
            MockSerial(interval_s=0.01),
            MockDetector(infer_delay_s=0.05),
        )
        table = s.run(seconds=0.8)
        self.assertGreaterEqual(len(table.rows), int(30 * 0.8 * 0.8))

    def test_drops_are_reported(self):
        s = Session(
            MockCamera(fps=30),
            MockSerial(interval_s=0.01),
            MockDetector(infer_delay_s=0.04),
        )
        table = s.run(seconds=1.0)
        self.assertGreater(table.meta["n_dropped_frames"], 0)

    def test_no_drop_when_detector_keeps_up(self):
        s = Session(
            MockCamera(fps=10),
            MockSerial(interval_s=0.01),
            MockDetector(infer_delay_s=0.01),
        )
        table = s.run(seconds=0.8)
        self.assertEqual(table.meta["n_dropped_frames"], 0)


class TestSerialNotBlockedByCamera(unittest.TestCase):
    def test_serial_polling_not_quantized_to_frame_period(self):
        fps = 30.0
        serial = RecordingSerial(interval_s=0.01)
        s = Session(BlockingCamera(fps=fps), serial, MockDetector(infer_delay_s=0.01))
        s.run(seconds=1.0)

        gaps = [b - a for a, b in zip(serial.poll_times, serial.poll_times[1:])]
        self.assertGreater(len(gaps), 10)
        # 串口与相机同线程时，poll 只在相机返回后成簇发生，
        # 间隔几乎都接近帧周期；拆分后应远小于半个帧周期。
        over = [g for g in gaps if g > (1.0 / fps) / 2]
        self.assertLess(len(over) / len(gaps), 0.1)


class TestLifecycle(unittest.TestCase):
    def test_threads_exit_and_devices_stopped_once(self):
        camera = CountingStream(MockCamera(fps=30))
        serial = CountingStream(MockSerial(interval_s=0.01))
        s = Session(camera, serial, MockDetector(infer_delay_s=0.01))
        s.run(seconds=0.3)

        self.assertEqual(camera.n_stop, 1)
        self.assertEqual(serial.n_stop, 1)
        alive = [t.name for t in threading.enumerate() if t.name.startswith("daqsync-")]
        self.assertEqual(alive, [])

    def test_detector_error_propagates(self):
        s = Session(MockCamera(fps=30), MockSerial(interval_s=0.01), BoomDetector())
        with self.assertRaises(RuntimeError):
            s.run(seconds=0.3)
        alive = [t.name for t in threading.enumerate() if t.name.startswith("daqsync-")]
        self.assertEqual(alive, [])

    def test_without_detector(self):
        s = Session(MockCamera(fps=30), MockSerial(interval_s=0.01), None)
        table = s.run(seconds=0.3)
        self.assertGreater(len(table.rows), 0)
        self.assertEqual(table.meta["n_detect_calls"], 0)
        self.assertEqual(table.meta["n_dropped_frames"], 0)

    def test_zero_seconds(self):
        s = Session(MockCamera(fps=30), MockSerial(interval_s=0.01), MockDetector())
        table = s.run(seconds=0.0)
        alive = [t.name for t in threading.enumerate() if t.name.startswith("daqsync-")]
        self.assertEqual(alive, [])
        # 线程起停之间可能已抓到一帧，故不要求表为空，只要求不崩且线程退净。
        self.assertLessEqual(len(table.rows), 2)

    def test_back_to_back_runs(self):
        s = Session(MockCamera(fps=30), MockSerial(interval_s=0.01), MockDetector())
        first = s.run(seconds=0.3)
        second = s.run(seconds=0.3)
        self.assertGreater(len(first.rows), 0)
        self.assertGreater(len(second.rows), 0)


if __name__ == "__main__":
    unittest.main()
