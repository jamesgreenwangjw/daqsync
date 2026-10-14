from __future__ import annotations

import time
from typing import Any, Optional

from ..clocks import Stamp, now_stamp
from .base import Sample, Stream


class MockCamera(Stream):
    """按 fps 产出假帧。poll 非阻塞；payload 是占位 dict。"""

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
    """OpenCV 真摄像头。

    时间戳是 grab() 成功、帧从驱动取走的时刻，不是 retrieve/解码结束，
    更不是推理结束。缓冲打到 1，降低 UVC 多帧排队造成的软件延迟。

    poll 会阻塞到下一帧（VideoCapture.grab 的行为）。MockCamera 才是非阻塞。
    """

    def __init__(self, index: int = 0, name: str = "cam0"):
        self.index = index
        self.name = name
        self._cap: Optional[Any] = None
        self._seq = 0
        self._running = False

    def start(self) -> None:
        import cv2

        self._cap = cv2.VideoCapture(self.index)
        if not self._cap.isOpened():
            raise RuntimeError(f"cannot open camera {self.index}")
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._running = True

    def stop(self) -> None:
        self._running = False
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def poll(self) -> Optional[Sample]:
        if not self._running or self._cap is None:
            return None
        ok = self._cap.grab()
        t_grab = time.perf_counter()
        if not ok:
            return None
        ok, frame = self._cap.retrieve()
        if not ok:
            return None
        seq = self._seq
        self._seq += 1
        stamp = Stamp(
            host_mono=t_grab,
            host_wall=time.time(),
            source=self.name,
            seq=seq,
        )
        return Sample(
            stamp=stamp,
            payload=frame,
            kind="frame",
            extras={"frame_id": seq, "grab_mono": t_grab},
        )
