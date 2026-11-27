# Ch23 主张、来源与验证边界

| 主张与正文位置 | 原始来源及定位 | 本章增量与独立验收 |
| --- | --- | --- |
| 23.1 相同对话文本可能对应不同业务结果 | 仓库 Ch36 Engine.run 的 after_commit 分支、TicketService.create 事务 | 调用上游本地服务，以相同操作键和新键分别重试，独立比较工单与审计计数 |
| 23.2 会话需要合法转移 | [W3C SCXML §3](https://www.w3.org/TR/scxml/#CoreIntroduction)，状态和转换 | 本地教学状态表由纯函数读取，不宣称实现 SCXML 解释器 |
| 23.3 读端重新应用历史须隔离外部作用 | [Fowler, Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)，Application State、External Updates | 回放程序只拿只读事件连接；业务库两项计数在各次恢复前后保持一致 |
| 23.3 快照附着于一致的事件前缀 | [SQLite Transactions §2](https://www.sqlite.org/lang_transaction.html)，[Isolation](https://www.sqlite.org/isolation.html)，[LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 中的 checkpoints | 同库事务写快照与事件，只读重开；模拟损坏、过期和异会话快照 |
| 23.4 传输游标和业务事件有不同的责任 | [HTML Server-sent events §9.2](https://html.spec.whatwg.org/multipage/server-sent-events.html)，Last-Event-ID；[CloudEvents](https://cloudevents.io/) 的事件元数据 | 本地序号必须连续，末尾丢失用权威后缀查询发现。样例传输是内存列表 |
| 23.5 重试和只读回放的可观察差异 | [RFC 9110 §9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)，[SQLite URI mode](https://www.sqlite.org/uri.html) | reports/replay.json 的 same_key_retry、transcript_only 和 cases：实际调用 SQLite 服务，网络故障为教学构造，无真实扣款 |

核验版本为本提交中的 Ch23 及所依赖的上游 Ch36。实验环境、运行命令、失败条件见同目录 README。人工独立复核待登记。
