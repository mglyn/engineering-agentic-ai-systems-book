# Exp-22-01　运行时负载实验

实验使用原创确定性任务图和模拟端点。执行器使用 Python 3.12 asyncio，时间用 perf_counter_ns 记录。源码、配置、图表和构造输入沿用仓库 MIT 许可。相同批次、相同下游容量、相同服务时长下，各策略运行五轮，另有三次故障注入。机器和解释器版本、逐任务参数、事件、耗时、资源峰值均在 reports/load.json。该报告归档的是本机一次实验，重跑时各项耗时会变化。

从仓库根目录运行：

```shell
python examples/ch22/async_runtime.py --output outputs/ch22/load.json
python examples/ch22/replay_load.py outputs/ch22/load.json
```

第一条在正常组中要求每轮 50 项完成，故障组区分取消、超时、可重派的调用前退出，收尾检查下游计数。第二条只读事件，逐项重建状态和执行份额，检查依赖放行顺序、租户额度、并发峰值和最终状态。原始数据与正文 Tab-22-03 同源。替换配置可直接传 --config，保持两个教学租户名称。依赖节点数由任务表生成策略决定。

| 主张 | 检查位置 | 证据范围 |
| --- | --- | --- |
| 有界组保护两个租户的执行份额 | replay_load.py 从每个 dispatch 到终态逐事件记账 | 单机协程，硬配额；不验证身份隔离 |
| 第一个交互任务更早完成 | 每轮取 interactive 的首个 done.ms，然后取五轮中位数 | 这一个扇出工作负载，策略同时改变了优先顺序和并发上限 |
| 取消与超时均阻断十个后继 | faults 中 batch-0 的终态和关联 blocked 事件 | 控制路径直接取消协程，未测远程模型资源释放 |
| 退出后可以重新派发本地只读任务 | worker_exit 故障中一次 worker_lost、第二次 dispatch、最终 done | 同一进程中一次 worker 协程异常退出，状态未丢失 |
| 就绪队列剩余容量不等于端点剩余容量 | peak_ready 和 peak_endpoint_wait 分别采集 | 有限批次保存在内存，无线上流量或 GPU 推理测量 |

本章直接使用的接口资料为 Python asyncio 的 Task cancellation、Queue、Semaphore 文档。对过载设计参照 Google SRE 的 Handling Overload，对超时和副作用查账参照 AWS Builders’ Library 的 Timeouts, retries, and backoff with jitter 与 Making retries safe with idempotent APIs。依赖语义与回放分别回链本书 Ch09、Ch23；容量指标定义回链 Ch27，真实工单事务回链 Ch36。正文图、配置、两租户实验及逐事件校验均为本书独立实现。
