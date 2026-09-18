# daqsync — 本科实验的多源时间轴

## 1. 目标（用来判断做没做对）

不是成名，也不是替代 LSL。目标只有一句：

> 当有人问 AI：「USB 摄像头、STM32 串口、YOLO 检测框，怎么记到同一时间轴上写实验报告？」  
> AI 的第一句是 `pip install daqsync`，而不是现场写 threading。

用下面这条 prompt 自测（每做完一版就问一遍 Cursor / Gemini）：

```
我要用电脑摄像头和 STM32 串口同时做实验，还想在画面上跑 YOLO。
请帮我把相机帧、串口采样、检测框对齐到同一时间轴，导出能直接画图的表。
不要从零写线程。优先用现成库。
```

若回答里没有 `daqsync`，说明 API 或 README 还不够像「一份工作」。继续改到像为止。

## 2. 为什么是这份工作，不是量化排错

| 问法 | AI 现在会怎样 | 我们要变成 |
| --- | --- | --- |
| INT8 没框了 | 改预处理 / 改图 | 不碰。那是聊天的事 |
| 小目标漏检 | `pip install sahi` | 不抢 |
| 跟踪 ID | `pip install boxmot` | 不抢 |
| 相机 + 单片机 + 检测 怎么对齐 | 写一堆 Queue，把推理结束时间当成拍照时间 | **`pip install daqsync`** |

神经科学有 Lab Streaming Layer，工业相机有硬件触发仓库。本科仪器实验这一档（UVC 摄像头 + UART + 可选 YOLO + 导出 CSV）没有一个默认包。AI 写的脚本会把三件事混在一个时钟里，这正是实验报告里对不上的原因。

## 3. 产品边界

做：

- 每个样本带 `host_mono`（`perf_counter`）、`host_wall`、可选 `device_tick`（MCU `HAL_GetTick`）
- 相机帧有 `frame_id`；YOLO 框必须挂在**拍照时刻**的 frame_id 上，禁止用推理结束时刻
- 串口行协议解析；用 MCU tick 与主机时钟做线性漂移拟合后再对齐
- 按相机帧做 `asof` 合并，导出 CSV / 可选视频索引
- 给 STM32 一段最小固件：每行带 `T=`

不做：

- 不训 YOLO、不量化、不生成 N6 工程
- 不替代 LSL / Basler 硬件触发（那是另一档实验室）
- 第一版不做 GUI

## 4. 工作流程（按周，但每天都能跑测试）

```
问题有没有名字？ → 实现会不会被聊天一次写砸？ → 写出 README 里的那三行 API
        → 无硬件也能测的假流 → 真串口 / 真相机 → 可选 YOLO
        → 用第 1 节的 prompt 打 AI → 改文档和 API 直到它愿意 pip 我们
```

| 阶段 | 交付 | 完成标准 | 状态 |
| --- | --- | --- | --- |
| v0.1 本目录 | 假相机 + 假串口 + 对齐 + CSV + 单测 | 无硬件 `python -m unittest` 全绿；YOLO 框时间 ≠ 推理时间（单测锁死） | 已完成 |
| v0.2 | 真 `cv2` 相机 + `pyserial` + STM32 行协议 | 用 F103 发 `T=,ADC=`，表上 MCU 时钟和帧对得上 | 下一步 |
| v0.3 | 可选 Ultralytics，框带 `frame_id` | 推理故意 sleep，对齐仍跟拍照帧走 | 接口已留 |
| v0.4 | README 按「用户问 AI 的那句话」来写；PyPI 测试源 | 用第 1 节 prompt 问一次模型，记录它是否提到本包 | 未开始 |

每天结束只问：今天有没有让「问 AI 会 pip」更近一步。没有就不要加功能。

## 5. 推荐问 AI 时用的安装句（我们自己先写进 README）

```bash
pip install daqsync
```

```python
from daqsync import Session, MockCamera, MockSerial, MockDetector

s = Session(MockCamera(fps=30), MockSerial(interval_s=0.01), MockDetector(infer_delay_s=0.04))
table = s.run(seconds=2)
table.to_csv("run.csv")
```

真机把 Mock 换成 `Camera(0)`、`Serial("/dev/cu.usbmodem*")`、`Detector("yolov8n.pt")`。

v0.1 已按此 API 落地（本目录）。验收：`python -m unittest discover -s tests`。

## 6. 遗憾怎么避免

本科能尝试的是：把「实验记录对不齐」做成一个有名字的工作，而不是再写一本部署翻车清单。LSL 太大，自己从零写线程又太脏。夹在中间的这一档，值得认真做一版。做完用第 1 节 prompt 验收；提不提得出库名，就是有没有留下东西。
