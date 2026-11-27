# F 部分的场景、资料与可复核贡献

书中的用户有一笔费用申请，可能在批任务排队时插话，在回执到达前断线，也可能指着票据说“换右边那张”。贯穿六章的问题是：**读者怎么查明这一次申请最终发生了什么？** 每章换一个观察位置。下列实验分别执行，使用相互关联的教学场景；六份报告来自不同运行。

| 章 | 从哪个问题写起 | 可对照的公开工作 | 本书在这个场景增加了什么 |
| --- | --- | --- | --- |
| 22 编排 | 财务批任务占满端点，交互用户多久能见到第一项？ | [asyncio 队列](https://docs.python.org/3.12/library/asyncio-queue.html)、[Google SRE 过载处理](https://sre.google/sre-book/handling-overload/) | 让两个租户竞争同一端点，保留每次派发与返回。五轮中位数里，无界方案吞吐最高，有界轮转方案让交互租户先得到结果。派发顺序与配额同时变化，表中保留了二者合并作用。[本地记录](ch22/runtime_load_report.md) |
| 23 会话 | 用户重连后，该补一条回执，还是再建一张单？ | [LangGraph 持久化](https://docs.langchain.com/oss/python/langgraph/persistence)、[事件溯源](https://martinfowler.com/eaaDev/EventSourcing.html)、SQLite | 三种终态分别经过二十种投递条件，再从独立连接查业务事实。读事件、以原键重试、换键重提的工单数及审计行数分别揭示三种不同作用。[回放记录](ch23/reports/replay.json) |
| 24 打断 | 用户按停，为什么旧句子还会播出来？ | [Python 任务取消](https://docs.python.org/3.12/library/asyncio-task.html#task-cancellation)、[LiveKit 轮次处理](https://docs.livekit.io/agents/logic/turns/) | 在片段入队、取走、迟到回调等固定位置打断，观察呈现端。每种策略四十个组合，旧片段越过停止点的组合数依次为 32、24、0；同时检查新轮输出。新增八组延迟指令与本地事务回执，比较轮次及代次复用时的错误裁决。[时序记录与复现入口](ch24/README.md) |
| 25 多模态 | “右边这张”指的是说话时的页面，还是最后到达的图片？ | [RTP 时钟](https://www.rfc-editor.org/rfc/rfc3550)、[WebVTT 时间线](https://www.w3.org/TR/webvtt1/)、LiveKit | 自制票据图、语音与受控事件到达顺序；让同一输入走两种证据绑定策略。十二个应选对象和八个应澄清用例分开报告，避免把一律拒绝计作安全改进。[逐例记录](ch25/reports/media.json) |
| 38 回归 | 两个客户端都说完成，如何把有错的候选留在发布线内？ | [Anthropic 的 agent 评估](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)、[OpenTelemetry traces](https://opentelemetry.io/docs/concepts/signals/traces/) | 复用第 37 章已有的重复建单对照；新增十二个固定切片，把业务终态、权限、工单与轨迹纳入判定。用三组单变量受控候选表明哪项改变触发暂缓。[回归记录](ch38/regression_report.md) |
| 39 发布 | 旧程序已回来，只读观察员还能审批吗？ | [Google SRE 金丝雀发布](https://sre.google/workbook/canarying-releases/)、[Kubernetes 回滚](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) | 复用第 36 章真实生成的本地 PRJ-3 工单库，构造环境错配与缓存残留。五次进程均正常返回，完整验收只通过三次；局部回滚唯一失败项是生效权限。[发布记录](ch39/release_report.md) |

[DeepSeek Harness 架构说明](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md)提供了一个可以对读的实现。读第 23、24 章时，尤其适合对照其持久会话事件和临时流片段的区分。本书在应用侧把观察延伸到数据库中的工单、实际采用的页面，以及停止后仍呈现的片段。仓库中的实验运行本书代码；报告里的数值不能解释为 DeepSeek 的表现。

基础工单接口、固定模型与三项目来自第 36 章，已知缺陷客户端及其独立判据来自第 37 章。F 部分的可复用产物是新增的输入、故障时点、对照条件、观察程序和原始记录。模型表现、真实语音识别准确率、物理扬声器停播延迟与生产运维能力需要各自的测量。

各主张的独立验收条件、正反例及适用范围见[工程证据索引](f_evidence_index.md)。
