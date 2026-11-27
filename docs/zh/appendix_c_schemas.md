# 附录 C　接口、模式与事件轨迹

同一笔工单申请，在计划图里是一条待执行任务，在工具服务里是一次带租户和审批校验的建单写入，在呈现层则对应某轮输出里的一条回执。排查“上一轮已经结束，为什么又收到回执”时，关键是拿着手头的 ID，知道该去哪份模式文件、哪条运行记录里查证。下文引用的模式版本和字段名均取自代码库，各章节各自维护其命名空间。

## C.1 从业务问题找到契约

| 想查的事 | 源码中的权威定义 | 怎样使用 |
| --- | --- | --- |
| 一项工作依赖哪些前置任务 | `examples/ch09/proposals/plan_schema.json`，`ch09-proposal-0.1` | 按计划 ID、版本号和任务列表定位前置依赖。该模式仍是 [Ch09 的教学提案](part3/ch09_task_decomposition_planning.md)，读取前先核对版本号。 |
| 收到的回复是否来自本次分派 | `examples/ch36/fixtures/study/message_schema.json`，`coordination-local-1` | 按 [Ch19](part5/ch19_multi_agent_communication.md) 的消息字段核对发送者、接收者、任务修订号、分派 epoch 和截止时间；重新分派后 epoch 会改变。 |
| 工具准备为哪个载荷建单 | `examples/ch36/src/book_reference/contracts.py` 的 payload_for 和 Approval；任务输入 `demo-1` | 操作 ID 按租户划定作用域，Approval 绑定载荷摘要；[Ch36](part9/ch36_reference_implementation.md) 的 TicketService 会拒绝同一操作键下的不同载荷。 |
| 回放可以走到哪一个状态 | `examples/ch23/event_schema.json` 与 `session_state_machine.yaml`，事件版本 1 | 按 [Ch23](part6/ch23_sessions_events_state.md) 的规则，用会话 ID 和连续序号恢复视图；旧版 v0 的 seq 可以迁移，遇到其他未知版本不能直接推进，需单独处理。 |
| 哪段输出还能呈现 | `examples/ch24/stream_interrupt_demo.py` 的 present 及原始运行记录 | [Ch24](part6/ch24_streaming_interrupts.md) 在单会话实验中按轮次和生成代次共同核对输出。呈现端的轮次与代次管界面归属，原工单的操作 ID 管业务查账，两者分开核对。 |

上面这几处接口各自维护不同类型的版本标识，查账时不能混用：计划版本记录目标与约束的修订；分派 epoch 区分接管前后的执行者；事件模式版本决定事件字段如何解析；轮次与生成代次合在一起，区分哪一轮对话以及同一轮里重新发起的哪一次输出。比如用户改了工单内容，建单载荷已经变化，沿用旧的审批摘要校验就会失败；反过来，如果只是恢复界面、重新显示原工单回执，业务状态没变，就不该给原工单再分配一个新的业务操作 ID。

## C.2 契约登记样例

| schema_id | 字段或事件 | 生产章 | 消费章 | 版本 | 兼容性 | 验证命令 | 维护人 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| book.session.event | 每会话的已确认状态事件及操作引用 | Ch23 | 附录 C；Ch24 引用其会话语义 | 1 | v0 的 seq 显式迁移为 sequence；未知编码不能推进本地游标 | `python examples/ch23/session_replay.py` | F |

运行上表中的验证命令，可以直接从输出的 JSON 里核对每个字段及取值。下面截取 completed 会话的最后一条事件，测试会把这条样例与重新运行的结果逐字段比对。

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

这条事件只在对应的本地实验会话里有效。ticket_id 为 1 只是数据库主键，不能单独拿来做跨租户授权；occurred_ms 为 1005 是实验构造的逻辑时间戳，不能用来推算网络延迟。要查实测恢复耗时，得看同一份报告中每条运行记录的 elapsed_us 字段。

## C.3 沿着一次缺失投递查账

打开 `outputs/ch23/replay.json`，在 cases 中定位 profile 为 completed、variant 为 missing_middle 的记录。这条用例里，快照停在序号 2，客户端依次收到序号 3 和 5；读端先应用 3，发现序号 4 缺失后从库中补读 4 和 5。回放结束时，sequence 为 5，status 为 completed，ticket_id 为 1。服务表在回放前后的计数始终是 [1, 1]（两项依次表示工单行数和审计行数），说明补读历史没有触发新的建单写入。

接着直接查看同一报告的顶层字段 same_key_retry：同一笔建单操作带原键重试后仍返回同一个 ticket_id，服务表计数变为 [1, 2]，即工单行数没变、审计行数加 1。再查看顶层字段 transcript_only：客户端只凭聊天文本重新提交并换用了新操作键，结果多建了一张工单，计数增至 [2, 3]。工单行对应实际生成的工单，审计行记录的是服务调用。如果把审计行数当成工单数，原键重试就会被误判为重复建单；如果只看客户端最后一次回复而不核对服务表计数，换键后多建的那张工单又会被漏掉。
