# 更新日志

本文件记录 daqsync 各版本的显著变更。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)规范。

## [未发布]

## [0.2.0] - 2026-10-14

### 新增

- `Session.run()` 增加 `frame_q_maxsize` 与 `serial_poll_s` 参数，分别控制待检测帧队列深度与串口线程轮询间隔。
- `FrameTable.summary()` 与 `FrameTable.meta` 增加 `n_dropped_frames`，报告因推理滞后而丢弃的待检帧数。
- 增加 `daqsync/py.typed` 类型标记，下游项目可对 daqsync 进行静态类型检查。

### 变更

- 串口采集拆分为独立线程，不再与相机采集共用轮询循环。
- 待检测帧队列由无界改为有界，队列满时丢弃最旧的待检帧。
- CI 测试矩阵扩展至 Linux / macOS / Windows 与 Python 3.9 / 3.13，并增加 mypy 类型检查。

### 修复

- 修复推理速度低于采集速度时，待检测帧队列无界增长导致 `infer_lag_s` 随运行时长线性上升的问题。
- 修复真实相机场景下，串口采样时间戳被相机帧周期量化的问题。
- 修复 `aligned_table()` 中局部变量遮蔽同名参数，导致 `meta["n_boxes"]` 取值为最后一帧检测框数的问题。
- 修复 `FrameTable.to_csv()` 未显式指定编码，在非 UTF-8 默认编码平台上产生乱码的问题。
- 修复 `fit_linear_clock()` 判定样本有限性时依赖自比较的写法。
- 移除 `streams/detector.py` 中未使用的导入。

## [0.1.0] - 2026-09-18

### 新增

- 首个公开版本。采集相机帧与串口采样，检测框按 `frame_id` 贴回采集帧，而非推理结束时刻。
- `MockCamera` / `MockSerial` / `MockDetector` 假流，无硬件即可运行。
- `Camera` / `Serial` 真机流（可选依赖 `opencv-python` / `pyserial`），`Detector` 封装 Ultralytics YOLO。
- STM32 行协议（`T=<HAL_GetTick>,ADC=<值>`）解析，并附带最小固件片段。
- 扁平 CSV 导出与 `daqsync` 命令行入口。

[未发布]: https://github.com/jamesgreenwangjw/daqsync/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/jamesgreenwangjw/daqsync/compare/v0.1.0...v0.2.0
[0.1.0]: https://pypi.org/project/daqsync/0.1.0/
