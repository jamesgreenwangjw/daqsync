from __future__ import annotations

import csv
from pathlib import Path
from typing import List

CSV_FIELDS = [
    "frame_id",
    "t_capture",
    "t_wall",
    "mcu_tick",
    "adc",
    "serial_lag_s",
    "infer_lag_s",
    "n_boxes",
    "conf_max",
]


def _fmt(value, digits=None):
    if value is None:
        return ""
    if digits is None:
        return str(value)
    return f"{value:.{digits}f}"


class FrameTable:
    def __init__(self, rows: List[dict], meta: dict):
        self.rows = rows
        self.meta = meta

    def __len__(self) -> int:
        return len(self.rows)

    def to_csv(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
            w.writeheader()
            for r in self.rows:
                w.writerow(
                    {
                        "frame_id": r.get("frame_id", ""),
                        "t_capture": _fmt(r.get("t_capture"), 6),
                        "t_wall": _fmt(r.get("t_wall"), 6),
                        "mcu_tick": r.get("mcu_tick", ""),
                        "adc": "" if r.get("adc") is None else r.get("adc"),
                        "serial_lag_s": _fmt(r.get("serial_lag_s"), 6),
                        "infer_lag_s": _fmt(r.get("infer_lag_s"), 6),
                        "n_boxes": r.get("n_boxes", 0),
                        "conf_max": _fmt(r.get("conf_max"), 4),
                    }
                )

    def summary(self) -> dict:
        lags = [r["infer_lag_s"] for r in self.rows if r.get("infer_lag_s") is not None]
        slags = [r["serial_lag_s"] for r in self.rows if r.get("serial_lag_s") is not None]
        return {
            "n": len(self.rows),
            "mean_infer_lag_s": sum(lags) / len(lags) if lags else None,
            "mean_serial_lag_s": sum(slags) / len(slags) if slags else None,
            "n_dropped_frames": self.meta.get("n_dropped_frames", 0),
            "clock_ab": self.meta.get("clock_ab"),
            "clock_note": self.meta.get("clock_note"),
        }
