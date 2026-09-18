from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, List


class FrameTable:
    def __init__(self, rows: List[dict], meta: dict):
        self.rows = rows
        self.meta = meta

    def __len__(self) -> int:
        return len(self.rows)

    def to_csv(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not self.rows:
            p.write_text("")
            return
        fieldnames = ["frame_id", "t_capture", "t_wall", "mcu_tick", "serial_lag_s", "infer_lag_s", "n_boxes", "serial_json", "boxes_json"]
        with p.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in self.rows:
                boxes = r.get("boxes") or []
                w.writerow(
                    {
                        "frame_id": r["frame_id"],
                        "t_capture": f"{r['t_capture']:.6f}",
                        "t_wall": f"{r['t_wall']:.6f}",
                        "mcu_tick": r.get("mcu_tick", ""),
                        "serial_lag_s": "" if r.get("serial_lag_s") is None else f"{r['serial_lag_s']:.6f}",
                        "infer_lag_s": "" if r.get("infer_lag_s") is None else f"{r['infer_lag_s']:.6f}",
                        "n_boxes": len(boxes) if boxes else 0,
                        "serial_json": json.dumps(r.get("serial"), ensure_ascii=False),
                        "boxes_json": json.dumps(boxes, ensure_ascii=False),
                    }
                )

    def summary(self) -> dict:
        lags = [r["infer_lag_s"] for r in self.rows if r.get("infer_lag_s") is not None]
        slags = [r["serial_lag_s"] for r in self.rows if r.get("serial_lag_s") is not None]
        return {
            "n": len(self.rows),
            "mean_infer_lag_s": sum(lags) / len(lags) if lags else None,
            "mean_serial_lag_s": sum(slags) / len(slags) if slags else None,
            "clock_ab": self.meta.get("clock_ab"),
        }
