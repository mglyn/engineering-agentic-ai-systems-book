# 第 24 章主张、来源与可复核范围

| 正文主张 | 原始资料及具体位置 | 书内证据与边界 |
| --- | --- | --- |
| 24.2 流式响应中的片段与最终可执行行动具有不同的生命周期 | [DeepSeek Harness 架构中的 session 与流事件](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md)，[第 12 章行动执行](../../docs/zh/part3/ch12_action_execution.md) | 本章在生成、入队、出队和呈现等处保留原始标识；课堂程序运行本书实现 |
| 24.3 满队列能阻塞异步生产者 | [Python 3.12 Queue.put](https://docs.python.org/3.12/library/asyncio-queue.html#asyncio.Queue.put) | interrupt_timeline.jsonl 的 full_queue；真实网络对端是否减速未测 |
| 24.3 高低水位可以分开设置 | [Python WriteTransport.set_write_buffer_limits](https://docs.python.org/3.12/library/asyncio-protocol.html#asyncio.WriteTransport.set_write_buffer_limits)，[Streams 的排队策略](https://streams.spec.whatwg.org/#qs) | [两组原始事件](reports/watermarks.json)按片段计量；网络字节缓冲与课堂队列分属不同位置 |
| 24.4 请求取消与任务退出有时间差 | [Python 3.12 Task.cancel](https://docs.python.org/3.12/library/asyncio-task.html#asyncio.Task.cancel)，[DOM 的中止活动](https://dom.spec.whatwg.org/#aborting-ongoing-activities) | 每个传播取消用例分别记录发送、捕获、退出与确认；协程启动前可能没有内部观察 |
| 24.4 账本中的工单和界面上的通知需要分别验收 | [第 36 章工单事务](../ch36/src/book_reference/storage.py)，[SQLite 只读 URI](https://www.sqlite.org/uri.html) | [8 组迟到控制/回执](reports/late_receipt.json)，每组新建数据库；固定任务与固定授权 |
| 24.5 计时间隔必须指定时间基准 | [W3C High Resolution Time 的 monotonic clock](https://www.w3.org/TR/hr-time-3/)，[Python perf_counter_ns](https://docs.python.org/3.12/library/time.html#time.perf_counter_ns) | 全部时点来自同一进程；没有测量声卡输出边界 |
| 24.5 用户打断还涉及播放端当时的位置 | [LiveKit 轮次与打断](https://docs.livekit.io/agents/logic/turns/) | 本章测应用呈现，设备到耳延迟待单独测量 |

## 章内覆盖与审阅入口

| Proposal 锚点 | 中文正文 | 对应交付 |
| --- | --- | --- |
| 24.1 Streaming model output and incremental actions | 24.1–24.2 | 片段生命周期、操作回执和可提交条件，Fig-24-01 |
| 24.2 Flow control, buffering, and stale-output cleanup | 24.3–24.4 | 高低水位实测、满队列、已出队片段与清理计数，Tab-24-01、02 |
| 24.3 Cancellation propagation and interruption latency | 24.4–24.6 | 重试及跨轮停止、120 条原始时间线、微秒拆分和验收，Fig-24-02、03 |

T1 对应 24.2，T2 对应片段身份与 JSONL 逐阶段记录，T3 对应两个队列实验，T4 对应 24.5 的时点定义，T5 覆盖上述三个锚点。本页记录作者核验；独立审稿身份与结果由实际审阅者填写。
