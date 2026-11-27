# 第 24 章样章与运行材料

[独立阅读样章](sample_ch24_zh.md)沿一笔被打断的工单追踪生成器、队列、呈现端与工具回执。源码和构造输入采用仓库 MIT 许可。实验在 Windows、CPython 3.12.16 上归档；执行下列命令需位于仓库根目录。标准库可以运行三项实验，绘图另需 Matplotlib。各项均使用本地 CPU 和教学数据。

| 实验 | 输入、对照与重复 | 预期现象 | 原始数据 |
| --- | --- | --- | --- |
| Exp-24-01 应用层打断 | 五个停止位置 × 两档容量 × 两类片段 × 是否重复停止；每组每策略一次 | 只改 UI、传播取消、再加清理与呈现前检查，各有 32、24、0 组残留。所有策略均应保留新轮输出 | [120 条时序](reports/interrupt_timeline.jsonl) |
| Exp-24-02 水位与唤醒 | 输入 24 个顺序片段，固定容量 4，两种低水位各运行一次 | 两组峰值均为 4，归档观察到 20、7 次等待，24 项均按序呈现 | [队列事件](reports/watermarks.json) |
| Exp-24-03 迟到停止与工具回执 | 固定业务申请，两个身份切换 × 四种接收规则，每格一个新 SQLite 库 | 工单八次都正确，四种组合会错误取消新流并显示旧回执 | [逐案独立查询与显示](reports/late_receipt.json) |

```shell
python examples/ch24/stream_interrupt_demo.py --output outputs/ch24/interrupt_timeline.jsonl
python examples/ch24/watermarks.py --output outputs/ch24/watermarks.json
python examples/ch24/late_receipt.py --output outputs/ch24/late_receipt.json
python -m pytest tests/test_ch24_interrupts.py
```

退出码 0 表示观测符合该对照的预期，包含按设计应当出错的旧策略。第一组用协程事件固定竞态位置；耗时用同一进程的单调时钟实测。先查每行 errors，再比较 expected_old、actual_old 和新代次的 present。测量字段里的 null 表示该时点没有观测。第二组按暂停与恢复事件定位唤醒，实际延时会受系统调度影响。第三组在 Ch36 完成真实本地事务后才释放延迟回执；若 UI 与预期不同，先看 switch_owner 与 delayed_stop，再看独立工单计数。

从已归档的同一份数据重绘正文 Fig-24-03，或更新供审阅的独立样章：

```shell
python examples/ch24/plot_tail.py examples/ch24/reports/interrupt_timeline.jsonl docs/images/ch24/old-tail.png
python examples/ch24/export_sample.py
```

样章的唯一编辑源是 [MkDocs 章稿](../../docs/zh/part6/ch24_streaming_interrupts.md)。导出会调整相对链接，使图和跨章链接可以在 GitHub 或本地仓库直接打开。实验不需要真实模型、声卡或云凭据。来源与中英锚点见[主张对照](claim_sources.md)。
