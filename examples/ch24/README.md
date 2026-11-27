# Exp-24-01 打断时序

本实验的代码、构造输入和日志采用本仓库 MIT 许可。在仓库根目录使用 Python 3.12。固定调度位置，每个组合运行一次，分别检验 3 种策略，时间戳单位为微秒。归档运行环境为 Windows、CPython 3.12.16。重复运行时事件计数应一致，时间分布会变化。

```shell
python examples/ch24/stream_interrupt_demo.py --output outputs/ch24/interrupt_timeline.jsonl
```

退出码 0 表示观察符合各自的预期，包括两种对照实现中预期出现的旧输出。超时或任何预期不符都应调查。每条记录的 phase、capacity、medium、repeated_stop 和 mode 一起标识一个用例。源码中固定的期望数量与实际 present 事件独立计数。查看 before_start 和 after_complete 可以看到相反的两个边界。

归档的原始记录在 reports/interrupt_timeline.jsonl。安装 Matplotlib 的绘图环境可从这份日志重新生成 Fig-24-03。

```shell
python examples/ch24/plot_tail.py examples/ch24/reports/interrupt_timeline.jsonl docs/images/ch24/old-tail.png
```

样章唯一编辑源为 docs/zh/part6/ch24_streaming_interrupts.md。演示使用内存中的呈现端与本地回执，不包含音频硬件、真实模型或远程事务。
