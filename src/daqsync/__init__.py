"""daqsync: 实验记录用的同一时间轴。"""

from .align import aligned_table
from .clocks import Stamp, now_stamp
from .session import Session
from .streams.camera import Camera, MockCamera
from .streams.detector import Detector, MockDetector
from .streams.serial import MockSerial, Serial, parse_kv_line
from .table import FrameTable

__version__ = "0.1.0"

__all__ = [
    "Session",
    "Camera",
    "MockCamera",
    "Serial",
    "MockSerial",
    "Detector",
    "MockDetector",
    "Stamp",
    "now_stamp",
    "aligned_table",
    "FrameTable",
    "parse_kv_line",
    "__version__",
]
