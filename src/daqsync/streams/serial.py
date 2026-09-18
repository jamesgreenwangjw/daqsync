from __future__ import annotations

import re
import time
from typing import Optional

from ..clocks import now_stamp
from .base import Sample, Stream

_KV = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^,\s]+)")


def parse_kv_line(line: str) -> dict:
    """T=1234,ADC=2048 → {'T': 1234.0 if numeric else str, ...}"""
    out = {}
    for k, v in _KV.findall(line):
        try:
            out[k] = float(v) if ("." in v or "e" in v.lower()) else int(v)
        except ValueError:
            out[k] = v
    return out


class MockSerial(Stream):
    """假装 MCU 按 interval 发 T=tick,ADC=...。device_tick 故意带一点漂移。"""

    def __init__(
        self,
        name: str = "mcu",
        interval_s: float = 0.01,
        drift_ppm: float = 50.0,
        start_tick: int = 1000,
    ):
        self.name = name
        self.interval_s = float(interval_s)
        self.drift_ppm = float(drift_ppm)
        self._tick = int(start_tick)
        self._seq = 0
        self._running = False
        self._next = 0.0
        self._t0 = 0.0

    def start(self) -> None:
        self._running = True
        self._t0 = time.perf_counter()
        self._next = self._t0

    def stop(self) -> None:
        self._running = False

    def poll(self) -> Optional[Sample]:
        if not self._running:
            return None
        now = time.perf_counter()
        if now < self._next:
            return None
        self._next += self.interval_s
        elapsed = now - self._t0
        # 故意：MCU 钟比 host 快 drift_ppm
        tick = int(self._tick + elapsed * 1000.0 * (1.0 + self.drift_ppm * 1e-6))
        seq = self._seq
        self._seq += 1
        adc = 2048 + int(200 * (seq % 50) / 50)
        line = f"T={tick},ADC={adc}"
        kv = parse_kv_line(line)
        stamp = now_stamp(self.name, seq, device_tick=float(tick))
        return Sample(stamp=stamp, payload=kv, kind="serial", extras={"raw": line})


class Serial(Stream):
    def __init__(self, port: str, baud: int = 115200, name: str = "mcu"):
        self.port = port
        self.baud = baud
        self.name = name
        self._ser = None
        self._buf = b""
        self._seq = 0
        self._running = False

    def start(self) -> None:
        import serial

        self._ser = serial.Serial(self.port, self.baud, timeout=0)
        self._running = True

    def stop(self) -> None:
        self._running = False
        if self._ser is not None:
            self._ser.close()
            self._ser = None

    def poll(self) -> Optional[Sample]:
        if not self._running or self._ser is None:
            return None
        chunk = self._ser.read(4096)
        if chunk:
            self._buf += chunk
        if b"\n" not in self._buf:
            return None
        line, self._buf = self._buf.split(b"\n", 1)
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            return None
        kv = parse_kv_line(text)
        tick = kv.get("T")
        seq = self._seq
        self._seq += 1
        stamp = now_stamp(
            self.name, seq, device_tick=float(tick) if tick is not None else None
        )
        return Sample(stamp=stamp, payload=kv, kind="serial", extras={"raw": text})
