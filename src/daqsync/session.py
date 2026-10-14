from __future__ import annotations

import queue
import threading
import time
from typing import List, Optional

from .align import aligned_table
from .streams.base import Sample, Stream
from .table import FrameTable

IDLE_SLEEP_S = 0.0005
DETECT_POLL_S = 0.05
JOIN_TIMEOUT_S = 2.0


def _enqueue_latest(q: "queue.Queue", item) -> bool:
    """非阻塞入队；队列已满时挤掉最旧的一项。

    返回是否发生了丢弃。全程不阻塞生产者，使检测线程处理的始终是
    最近采集的帧，而不是积压队列里最旧的那一帧。
    """
    try:
        q.put_nowait(item)
        return False
    except queue.Full:
        pass
    try:
        q.get_nowait()
    except queue.Empty:
        pass
    try:
        q.put_nowait(item)
    except queue.Full:
        # 单生产者单消费者下不可达；兜底以免把丢弃退化成异常。
        return True
    return True


class Session:
    """相机、串口、推理各占一条线程，帧经有界队列交给推理。

    相机的 ``poll()`` 在真实设备上会阻塞到下一帧（约一个帧周期）。若串口
    读与相机读共用一条线程，串口样本的时间戳会被该帧周期量化，因此串口
    单独占用一条线程。

    推理慢于采集时，队列丢弃最旧的待检帧，检测框始终贴近采集时刻，
    ``infer_lag_s`` 有界；代价是部分帧没有检测结果。
    """

    def __init__(self, camera: Stream, serial: Stream, detector=None):
        self.camera = camera
        self.serial = serial
        self.detector = detector
        self.frames: List[Sample] = []
        self.serials: List[Sample] = []
        self.boxes: List[Sample] = []

    def run(
        self,
        seconds: float = 2.0,
        detect_every: int = 1,
        frame_q_maxsize: int = 1,
        serial_poll_s: float = IDLE_SLEEP_S,
    ) -> FrameTable:
        """采集 ``seconds`` 秒，返回对齐后的表。

        ``detect_every`` 按帧序号静态降采样；``frame_q_maxsize`` 限制待检
        队列深度，满则丢弃最旧帧。二者独立：降采样后产率仍高于推理产能时
        才会发生丢弃，被检测的 ``frame_id`` 因而不等间隔。
        """
        self.frames.clear()
        self.serials.clear()
        self.boxes.clear()

        detect_every = max(1, int(detect_every))
        maxsize = max(1, int(frame_q_maxsize))

        started: List[Stream] = []
        try:
            self.camera.start()
            started.append(self.camera)
            self.serial.start()
            started.append(self.serial)
        except BaseException:
            for stream in reversed(started):
                try:
                    stream.stop()
                except BaseException:
                    pass
            raise

        stop = threading.Event()
        capture_done = threading.Event()
        frame_q: queue.Queue = queue.Queue(maxsize=maxsize)
        errors: List[BaseException] = []
        lock = threading.Lock()
        detect_on = self.detector is not None
        n_dropped = 0

        def note_error(exc: BaseException) -> None:
            with lock:
                errors.append(exc)
            stop.set()

        def capture_loop() -> None:
            nonlocal n_dropped
            try:
                while not stop.is_set():
                    f = self.camera.poll()
                    if f is None:
                        time.sleep(IDLE_SLEEP_S)
                        continue
                    with lock:
                        self.frames.append(f)
                    if detect_on and (f.stamp.seq % detect_every == 0):
                        if _enqueue_latest(frame_q, f):
                            n_dropped += 1
            except BaseException as exc:
                note_error(exc)
            finally:
                capture_done.set()

        def serial_loop() -> None:
            try:
                while not stop.is_set():
                    while True:
                        s = self.serial.poll()
                        if s is None:
                            break
                        with lock:
                            self.serials.append(s)
                    time.sleep(serial_poll_s)
            except BaseException as exc:
                note_error(exc)

        def detect_loop() -> None:
            try:
                while True:
                    try:
                        f = frame_q.get(timeout=DETECT_POLL_S)
                    except queue.Empty:
                        if capture_done.is_set() and frame_q.empty():
                            break
                        continue
                    box = self.detector.detect(f)
                    with lock:
                        self.boxes.append(box)
            except BaseException as exc:
                note_error(exc)

        cap_th = threading.Thread(target=capture_loop, name="daqsync-capture")
        ser_th = threading.Thread(target=serial_loop, name="daqsync-serial")
        det_th: Optional[threading.Thread] = None
        if detect_on:
            det_th = threading.Thread(target=detect_loop, name="daqsync-detect")

        cap_th.start()
        ser_th.start()
        if det_th is not None:
            det_th.start()

        try:
            deadline = time.perf_counter() + max(0.0, seconds)
            while not stop.is_set():
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    break
                stop.wait(timeout=min(DETECT_POLL_S, remaining))
        finally:
            stop.set()
            cap_th.join(timeout=JOIN_TIMEOUT_S)
            ser_th.join(timeout=JOIN_TIMEOUT_S)
            if det_th is not None:
                det_th.join(timeout=JOIN_TIMEOUT_S)
            self.camera.stop()
            self.serial.stop()
            cap_th.join(timeout=IDLE_SLEEP_S)
            ser_th.join(timeout=IDLE_SLEEP_S)
            if det_th is not None:
                det_th.join(timeout=IDLE_SLEEP_S)

        if errors:
            raise errors[0]

        rows, meta = aligned_table(self.frames, self.serials, self.boxes)
        meta["n_detect_calls"] = len(self.boxes)
        meta["n_dropped_frames"] = n_dropped
        meta["clock_note"] = "clock_ab is diagnostic only; asof uses host_mono"
        return FrameTable(rows, meta)
