from __future__ import annotations

import time
from typing import List

from .align import aligned_table
from .streams.base import Sample, Stream
from .streams.detector import MockDetector
from .table import FrameTable


class Session:
    def __init__(self, camera: Stream, serial: Stream, detector=None):
        self.camera = camera
        self.serial = serial
        self.detector = detector
        self.frames: List[Sample] = []
        self.serials: List[Sample] = []
        self.boxes: List[Sample] = []

    def run(self, seconds: float = 2.0, detect_every: int = 1) -> FrameTable:
        self.camera.start()
        self.serial.start()
        t_end = time.perf_counter() + seconds
        n_det = 0
        try:
            while time.perf_counter() < t_end:
                while True:
                    s = self.serial.poll()
                    if s is None:
                        break
                    self.serials.append(s)
                f = self.camera.poll()
                if f is not None:
                    self.frames.append(f)
                    if self.detector is not None and (f.stamp.seq % detect_every == 0):
                        self.boxes.append(self.detector.detect(f))
                        n_det += 1
                time.sleep(0.0005)
        finally:
            self.camera.stop()
            self.serial.stop()
        rows, meta = aligned_table(self.frames, self.serials, self.boxes)
        meta["n_detect_calls"] = n_det
        return FrameTable(rows, meta)
