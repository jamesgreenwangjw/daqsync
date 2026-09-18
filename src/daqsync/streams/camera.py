from __future__ import annotations

import time
from typing import Optional

from ..clocks import now_stamp
from .base import Sample, Stream


class MockCamera(Stream):
    """按 fps 产出假帧。payload 是 {height,width} 的 uint8 数组或占位 dict。"""

    def __init__(self, name: str = "cam0", fps: float = 30.0, size=(64, 64)):
        self.name = name
        self.fps = float(fps)
        self.size = size
        self._seq = 0
        self._running = False
        self._next = 0.0

    def start(self) -> None:
        self._running = True
        self._next = time.perf_counter()

    def stop(self) -> None:
        self._running = False

    def poll(self) -> Optional[Sample]:
        if not self._running:
            return None
        now = time.perf_counter()
        if now < self._next:
            return None
        self._next += 1.0 / self.fps
        seq = self._seq
        self._seq += 1
        h, w = self.size
        stamp = now_stamp(self.name, seq)
        return Sample(
            stamp=stamp,
            payload={"h": h, "w": w, "seq": seq},
            kind="frame",
            extras={"frame_id": seq},
        )


class Camera(Stream):
    """OpenCV 真摄像头。capture 时刻打 Stamp，不是 read() 返回之后再打。"""

    def __init__(self, index: int = 0, name: str = "cam0"):
        self.index = index
        self.name = name
        self._cap = None
        self._seq = 0
        self._running = False

    def start(self) -> None:
        import cv2

        self._cap = cv2.VideoCapture(self.index)
        if not self._cap.isOpened():
            raise RuntimeError(f"cannot open camera {self.index}")
        self._running = True

    def stop(self) -> None:
        self._running = False
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def poll(self) -> Optional[Sample]:
        if not self._running or self._cap is None:
            return None
        t0 = time.perf_counter()
        ok, frame = self._cap.read()
        if not ok:
            return None
        seq = self._seq
        self._seq += 1
        stamp = now_stamp(self.name, seq)
        # 用 read 前后均值近似曝光中点；更严的做法留给 v0.2 V4L2
        return Sample(
            stamp=stamp,
            payload=frame,
            kind="frame",
            extras={"frame_id": seq, "grab_mono": t0},
        )
