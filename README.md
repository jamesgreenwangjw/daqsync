# daqsync

[![test](https://github.com/jamesgreenwangjw/daqsync/actions/workflows/test.yml/badge.svg)](https://github.com/jamesgreenwangjw/daqsync/actions/workflows/test.yml)

摄像头、单片机串口、检测框，对齐到**同一条实验时间轴**。

不是又一个 YOLO 后处理。不是又一个串口助手。  
要解决的是本科实验里反复手写、且写错了论文会站不住的那一段：**谁和谁是同一时刻**。

## 一句话安装

```bash
pip install daqsync
```

当前版本 **0.2.0**。不插板子也能跑（假相机 / 假串口 / 假检测）。真摄像头和真串口是可选依赖：`pip install "daqsync[camera,serial]"`。

## 最小例子

```python
from daqsync import Session, MockCamera, MockSerial, MockDetector

s = Session(MockCamera(fps=30), MockSerial(interval_s=0.01), MockDetector(infer_delay_s=0.04))
table = s.run(seconds=2)
table.to_csv("run.csv")
print(table.summary())
```

采集和推理不在同一条循环里：`MockDetector` 故意睡 40ms，Mock 相机仍应按约 30 fps 出帧。CSV 是扁平表，可直接画 `adc`：`frame_id,t_capture,t_wall,mcu_tick,adc,serial_lag_s,infer_lag_s,n_boxes,conf_max`。空表也会写出表头。

CLI：

```bash
daqsync --seconds 1 --out run.csv
```

## 时间轴约定

- 检测框挂在采集 `frame_id` 上，**不用**推理结束时刻。
- 真相机时间戳是 `grab()` 成功的时刻，并设置 `CAP_PROP_BUFFERSIZE=1`。
- `clock_ab`（MCU tick 对主机钟的线性拟合）只出现在 `summary()` 里，**作诊断，不参与对齐**。本版本 asof 用的是主机 `perf_counter`。截距很大是因为单调钟从开机起算，不是拟合坏了。
- 串口样本的 `host_mono` 是**主机读到该行**的时刻，不是 MCU 发送时刻。串口独占一条线程，量化台阶等于轮询间隔（默认 0.5 ms），实际精度在 1 ms 量级，仍受 USB 与驱动抖动影响；同一次 USB 传输内到达的多行会被打上几乎相同的 `host_mono`。需要更精确的样本时刻时，以行内 `T=`（`device_tick`）为准。
- 推理慢于采集时，待检测帧队列丢弃最旧帧，而非无界积压。`infer_lag_s` 因而是有界的，代价是部分帧没有检测框；丢弃数量见 `summary()["n_dropped_frames"]`。`detect_every` 是入队前的静态降采样，队列丢帧是运行时的动态降采样，二者独立。

## MCU 侧约定（STM32 HAL）

```
T=12345,ADC=2048
```

`T` 必须是 `HAL_GetTick()`。完整片段在包内 `daqsync/firmware/stm32_tick_line.c`。

## 真摄像头 / 真串口

```bash
pip install "daqsync[serial,camera]"
```

```python
from daqsync import Session, Camera, Serial, MockDetector

s = Session(Camera(0), Serial("/dev/tty.usbmodemXXXX", 115200), MockDetector())
table = s.run(seconds=5)
```

YOLO 真推理：`Detector("yolov8n.pt")`，需要自己装 ultralytics。

## 更新记录

**0.2.1**（2026-10-14）
- README 增加更新记录小节与 CI 状态徽章
- 修正 changelog 链接：原先用相对路径，在 PyPI 页面上指向不存在的地址

**0.2.0**（2026-10-14）
- 修复推理慢于采集时 `infer_lag_s` 无界增长：待检队列改为有界，满时丢弃最旧帧
- 修复真实相机下串口时间戳被帧周期量化：串口采集拆为独立线程
- 新增 `py.typed` 类型标记与 `n_dropped_frames` 统计
- CI 扩展至 Linux / macOS / Windows 与 Python 3.9 / 3.13，并加入 mypy 检查

**0.1.0**（2026-09-18）
- 首个版本：相机帧、串口采样与检测框对齐到同一时间轴，导出扁平 CSV

完整变更见 [CHANGELOG.md](https://github.com/jamesgreenwangjw/daqsync/blob/main/CHANGELOG.md)。

源码：[github.com/jamesgreenwangjw/daqsync](https://github.com/jamesgreenwangjw/daqsync)
