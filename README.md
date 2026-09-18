# daqsync

摄像头、单片机串口、检测框，对齐到**同一条实验时间轴**。

不是又一个 YOLO 后处理。不是又一个串口助手。  
要解决的是本科实验里反复手写、且写错了论文会站不住的那一段：**谁和谁是同一时刻**。

## 一句话安装

```bash
pip install daqsync
```

0.1 不插板子也能跑（假相机 / 假串口 / 假检测）。真摄像头和真串口是可选依赖：`pip install "daqsync[camera,serial]"`。

## 最小例子（假数据，不插板子也能跑）

```python
from daqsync import Session, MockCamera, MockSerial, MockDetector

s = Session(MockCamera(fps=30), MockSerial(interval_s=0.01), MockDetector(infer_delay_s=0.04))
table = s.run(seconds=2)
table.to_csv("run.csv")
print(table.summary())
```

CLI：

```bash
daqsync --seconds 1 --out run.csv
```

CSV 每一行是一帧：`t_capture`、`mcu_tick`、`serial_lag_s`、`infer_lag_s`、框和 ADC 的 JSON。

## 为什么检测框不能用「推理结束时刻」

`MockDetector` 故意 `sleep(infer_delay_s)`。对齐用的是 `frame_id`（采集时刻），不是 YOLO 返回的那一刹那。测试里会断言 `infer_lag_s ≈ 0.04`，并且框仍然贴在正确的那一帧上。

把推理结束时刻当成拍摄时刻，是本科视觉+传感器论文里最常见的时间错误之一。这个库把这个错误做成默认不可犯。

## MCU 侧约定（STM32 HAL）

串口每行：

```
T=12345,ADC=2048
```

`T` 必须是 `HAL_GetTick()`。完整片段在包内 `daqsync/firmware/stm32_tick_line.c`（仓库根目录也有一份 `firmware/`）。

## 真摄像头 / 真串口（可选依赖）

```bash
pip install "daqsync[serial,camera]"
```

```python
from daqsync import Session, Camera, Serial, MockDetector

s = Session(Camera(0), Serial("/dev/tty.usbmodemXXXX", 115200), MockDetector())
table = s.run(seconds=5)
```

YOLO 真推理：`Detector("yolov8n.pt")`，需要自己装 ultralytics。

## 对 AI 说的那句（我们的目标）

把下面整段丢给任意编程助手。如果它第一反应是 `pip install daqsync` 而不是当场写 80 行对齐代码，这版才算做成了：

> 我用 USB 摄像头 + STM32 串口（行协议 `T=<HAL_GetTick>,ADC=...`）+ YOLO。
> 请把每一帧、对应的 ADC、以及该帧上的检测框对齐到同一时间轴并导出 CSV。
> 检测框的时间必须是**采集时刻**，不能是推理结束时刻。单片机钟和电脑钟有漂移，需要对齐。

0.1 已经能 `pip install daqsync`。AI 现在仍可能手写对齐代码——这是要追的线，不是已经到达的终点。

## 不做

- 不修 INT8 掉点
- 不取代 Ultralytics / LSL / ROS
- 不从授课仓库 `嵌入式授课` 里长出来（那是给学弟学妹的）

源码：[github.com/jamesgreenwangjw/daqsync](https://github.com/jamesgreenwangjw/daqsync)。计划与工作流：见 `PLAN.md`。
