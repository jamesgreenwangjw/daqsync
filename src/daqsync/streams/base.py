from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from ..clocks import Stamp


@dataclass
class Sample:
    stamp: Stamp
    payload: Any
    kind: str  # "frame" | "serial" | "boxes"
    extras: dict = field(default_factory=dict)


class Stream(ABC):
    name: str

    @abstractmethod
    def start(self) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...

    @abstractmethod
    def poll(self) -> Optional[Sample]:
        """取一个样本，没有则 None。

        Mock 流是非阻塞的。真相机的 grab() 会等到下一帧。
        """

    def close(self) -> None:
        self.stop()
