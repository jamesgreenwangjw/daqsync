from __future__ import annotations

from typing import List

from .clocks import fit_linear_clock
from .streams.base import Sample


def asof_join(left_times, left_rows, right_times, right_rows, tolerance: float):
    """把 right 按时间贴到 left 上：每个 left 取不超过它、且 |dt|<tolerance 的最近 right。"""
    j = 0
    n = len(right_times)
    out = []
    for t, row in zip(left_times, left_rows):
        while j + 1 < n and right_times[j + 1] <= t:
            j += 1
        if n == 0:
            out.append((row, None, None))
            continue
        cand = j if right_times[j] <= t else max(0, j - 1)
        dt = t - right_times[cand]
        if 0 <= dt <= tolerance:
            out.append((row, right_rows[cand], dt))
        else:
            out.append((row, None, None))
    return out


def aligned_table(
    frames: List[Sample],
    serials: List[Sample],
    boxes: List[Sample],
    serial_tolerance_s: float = 0.02,
):
    """一帧一行。

    - MCU 用 host_mono asof（v0.1）；有 device_tick 时同时拟合漂移写进 meta。
    - YOLO 框按 extras['frame_id'] 贴到同一帧，**不用** boxes.stamp（那是推理结束时刻）。
    """
    box_by_fid = {}
    for b in boxes:
        fid = b.extras.get("frame_id")
        box_by_fid[fid] = b

    ticks = [s.stamp.device_tick for s in serials if s.stamp.device_tick is not None]
    monos = [s.stamp.host_mono for s in serials if s.stamp.device_tick is not None]
    clock_ab = fit_linear_clock(monos, ticks) if ticks else None

    ft = [f.stamp.host_mono for f in frames]
    st = [s.stamp.host_mono for s in serials]
    joined = asof_join(ft, frames, st, serials, serial_tolerance_s)

    rows = []
    for frame, ser, dt in joined:
        fid = frame.extras.get("frame_id", frame.stamp.seq)
        box = box_by_fid.get(fid)
        row = {
            "frame_id": fid,
            "t_capture": frame.stamp.host_mono,
            "t_wall": frame.stamp.host_wall,
            "serial": None if ser is None else ser.payload,
            "serial_lag_s": dt,
            "boxes": None if box is None else box.payload,
            "t_infer_end": None if box is None else box.stamp.host_mono,
            "infer_lag_s": None
            if box is None
            else (box.stamp.host_mono - frame.stamp.host_mono),
        }
        if ser is not None and ser.stamp.device_tick is not None:
            row["mcu_tick"] = ser.stamp.device_tick
        rows.append(row)

    meta = {"clock_ab": clock_ab, "n_frames": len(frames), "n_serial": len(serials), "n_boxes": len(boxes)}
    return rows, meta
