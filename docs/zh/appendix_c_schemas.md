# 附录 C　接口、模式与事件轨迹

同一笔申请在计划图里是一个待执行的节点，在工具服务里是一次有权限边界的写入，在用户屏幕上又可能只是半句提示。排查“上一轮已经结束，为什么还收到了回执”时，需要知道能拿哪个 ID 去哪一层查。本附录给出教学实现的查找入口和一笔可以逐步复核的记录。模式版本取自代码库；不同章节使用各自负责的命名空间。

## C.1 从业务问题找到契约

| 想查的事 | 源码中的权威定义 | 怎样使用 |
| --- | --- | --- |
| 一项工作依赖哪些前置任务 | `examples/ch09/proposals/plan_schema.json`，`ch09-proposal-0.1` | 从计划 ID、版本和任务表追到依赖。该模式仍是 [Ch09 的教学提案](part3/ch09_task_decomposition_planning.md)。消费前核对版本。 |
| 收到的回复是否来自本次分派 | `examples/ch36/fixtures/study/message_schema.json`，`coordination-local-1` | 在 [Ch19](part5/ch19_multi_agent_communication.md) 检查发送者、接收者、任务修订、分派 epoch 和截止时间。epoch 随重新分派改变。 |
| 工具准备为哪个载荷建单 | `examples/ch36/src/book_reference/contracts.py` 的 payload_for 和 Approval；任务输入 `demo-1` | 用租户限定操作 ID 的作用域，审批绑定载荷摘要。[Ch36](part9/ch36_reference_implementation.md) 的 TicketService 拒绝同一键下的另一份载荷。 |
| 回放可以走到哪一个状态 | `examples/ch23/event_schema.json` 与 `session_state_machine.yaml`，事件版本 1 | [Ch23](part6/ch23_sessions_events_state.md) 按会话身份和连续序号恢复视图。旧格式 v0 的 seq 可以迁移，其他未知版本需处理。 |
| 哪段输出还能呈现 | `examples/ch24/stream_interrupt_demo.py` 的 present 及原始运行记录 | [Ch24](part6/ch24_streaming_interrupts.md) 在单会话实验中按代次核对。呈现时的代次和原工单的操作 ID 分别解决界面归属与业务查账。 |

这些接口使用了多种“版本”。计划版本记录目标与约束的修订；分派 epoch 区分接管前后的执行者；事件模式版本说明字节如何解释；生成代次区分同一轮重新发起的输出。例如用户要求修改金额，建单载荷已经改变，沿用旧的审批摘要会失败。仅仅恢复界面、重新显示原工单回执，则不应为旧工单创建一个新业务身份。

## C.2 填好的登记项

| schema_id | 字段或事件 | 生产章 | 消费章 | 版本 | 兼容性 | 验证命令 | 维护人 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| book.session.event | 每会话的已确认状态事件及操作引用 | Ch23 | 附录 C；Ch24 引用其会话语义 | 1 | v0 的 seq 显式迁移为 sequence；未知编码不能推进本地游标 | `python examples/ch23/session_replay.py` | F |

记录的字段和值可以从命令输出的 JSON 直接取得。下面列出 completed 会话的最后一条；测试会把本页的样例与重跑结果逐字段比较。

```json
{
  "schema_version": 1,
  "session_id": "completed",
  "turn_id": "turn-1",
  "event_id": "completed-5",
  "sequence": 5,
  "occurred_ms": 1005,
  "kind": "completed",
  "operation_id": "T-DEMO-01-completed:1:create",
  "ticket_id": 1
}
```

这条记录只在它所在的本地实验会话中有意义。票号 1 是数据库主键，不能单独当作跨租户授权。1005 是构造的逻辑时间，不能拿来计算网络延迟。实测恢复耗时在同一报告每条运行记录的 elapsed_us 字段中。

## C.3 沿着一次缺失投递查账

打开 `outputs/ch23/replay.json`，在 cases 中取 profile 为 completed、variant 为 missing_middle 的记录。快照停在序号 2，客户端依次收到 3 和 5。读端先应用 3，再发现 4 尚未到达，因而从库中补读 4 和 5。最终 sequence 是 5，status 是 completed，ticket_id 是 1。服务表在回放前后的计数都是 [1, 1]，两项依次表示工单行数和审计行数。

接着查看 same_key_retry。同一笔操作的重试返回同一票号，计数变成 [1, 2]。最后看 transcript_only，示范客户端只依据聊天文本换键重新提交，计数增至 [2, 3]。三组证据共享原始载荷。通过这两个计数就能区分读历史、重复调用服务、新产生业务作用。若把审计记录也当成工单数，第二步会被误报为重复扣费；若只统计客户端最后一次回复，第三步又会被漏掉。
