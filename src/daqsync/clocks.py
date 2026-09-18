from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Stamp:
    """一次入队时刻。

    host_mono: 单调钟，用来测间隔和漂移，不受对时打扰。
    host_wall: wall clock，方便实验日志。
    device_tick: 单片机毫秒（HAL_GetTick），没有则为 None。
    seq: 该源流内序号。
    source: 流名。
    """

    host_mono: float
    host_wall: float
    source: str
    seq: int
    device_tick: Optional[float] = None


def now_stamp(source: str, seq: int, device_tick: Optional[float] = None) -> Stamp:
    return Stamp(
        host_mono=time.perf_counter(),
        host_wall=time.time(),
        source=source,
        seq=int(seq),
        device_tick=device_tick,
    )


def fit_linear_clock(host_mono, device_tick):
    """device_tick ≈ a * host_mono + b。至少 4 个有限样本，否则 None。纯 Python，不依赖 numpy。"""
    pairs = [
        (float(h), float(d))
        for h, d in zip(host_mono, device_tick)
        if h == h and d == d  # NaN 检查
    ]
    n = len(pairs)
    if n < 4:
        return None
    sx = sy = sxx = sxy = 0.0
    for h, d in pairs:
        sx += h
        sy += d
        sxx += h * h
        sxy += h * d
    den = n * sxx - sx * sx
    if abs(den) < 1e-18:
        return None
    a = (n * sxy - sx * sy) / den
    b = (sy - a * sx) / n
    return float(a), float(b)


def device_to_host(device_tick, ab) -> float:
    a, b = ab
    return (float(device_tick) - b) / a
