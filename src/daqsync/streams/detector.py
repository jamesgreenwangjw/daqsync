from __future__ import annotations

import time
from typing import Optional

from ..clocks import now_stamp
from .base import Sample, Stream


class MockDetector:
    """把帧变成假框。infer_delay_s 模拟推理耗时，用来证明对齐不能用推理结束时刻。"""

    def __init__(self, name: str = "yolo", infer_delay_s: float = 0.04, n_boxes: int = 1):
        self.name = name
        self.infer_delay_s = float(infer_delay_s)
        self.n_boxes = int(n_boxes)
        self._seq = 0

    def detect(self, frame_sample: Sample) -> Sample:
        time.sleep(self.infer_delay_s)
        seq = self._seq
        self._seq += 1
        boxes = [
            {"xyxy": [10, 10, 40, 40], "cls": 0, "conf": 0.9, "frame_id": frame_sample.extras["frame_id"]}
            for _ in range(self.n_boxes)
        ]
        # Stamp 是「推理结束」——故意和 capture 不同。对齐必须用 frame_id。
        stamp = now_stamp(self.name, seq)
        return Sample(
            stamp=stamp,
            payload=boxes,
            kind="boxes",
            extras={
                "frame_id": frame_sample.extras["frame_id"],
                "capture_mono": frame_sample.stamp.host_mono,
                "infer_end_mono": stamp.host_mono,
            },
        )


class Detector:
    """可选：包一层 ultralytics。没有安装就不要用这个类。"""

    def __init__(self, model_path: str = "yolov8n.pt", name: str = "yolo"):
        from ultralytics import YOLO

        self.model = YOLO(model_path)
        self.name = name
        self._seq = 0

    def detect(self, frame_sample: Sample) -> Sample:
        frame = frame_sample.payload
        res = self.model.predict(frame, verbose=False)[0]
        boxes = []
        if res.boxes is not None:
            for b in res.boxes:
                xyxy = b.xyxy[0].tolist()
                boxes.append(
                    {
                        "xyxy": xyxy,
                        "cls": int(b.cls[0]),
                        "conf": float(b.conf[0]),
                        "frame_id": frame_sample.extras["frame_id"],
                    }
                )
        seq = self._seq
        self._seq += 1
        stamp = now_stamp(self.name, seq)
        return Sample(
            stamp=stamp,
            payload=boxes,
            kind="boxes",
            extras={
                "frame_id": frame_sample.extras["frame_id"],
                "capture_mono": frame_sample.stamp.host_mono,
                "infer_end_mono": stamp.host_mono,
            },
        )
