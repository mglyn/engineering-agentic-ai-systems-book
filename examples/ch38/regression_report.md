# Exp-38-01　两个客户端都说已完成

实验基线为 Ch36 参考引擎和 Ch37 的 buggy/fixed 缺陷对照。本章在它们之上新增三组单因素候选、十二个预先登记的业务切片、九种注入、断言和逐项报告。素材和代码来自本仓库或为本书原创，沿用 MIT 许可。记录生成环境为 Windows 和 Python 3.12；具体解释器与 SQLite 版本在每份 gate 报告中。每组一次、每切片最多进入引擎两次。任务、政策、代码和输入摘要随报告记录。摘要用于辨认字节差异，不能替代制品签名或团队批准。

| 输入或对照 | 预期/实测 | 原始记录 | 出现差异时的处置 |
| --- | --- | --- | --- |
| Ch37 同一任务，错误客户端重试时换键 | completed，2 个创建，独立验收失败 | reports/probe-buggy.json | 保留为负对照；只看回复的测试会漏报 |
| Ch37 客户端沿用原操作 ID | completed，1 个创建，验收通过 | reports/probe-fixed.json | 重跑前新建独立输出目录 |
| Ch38 全切片 | 12/12 通过 | reports/baseline.json | 工具服务、客户端、金标与规则分开定位 |
| 固定模型切换 | 主管切片失去正确的原因，暂缓 | reports/diff-model-change.json | 检查提案和授权后继；不得放宽原因断言 |
| 脚本化提示切换 | 11 个切片未通过 | reports/diff-prompt-change.json | 核原始回复引用，再追执行器的政策判定 |
| 截止时刻切换 | 10 个切片未通过 | reports/diff-config-change.json | 核逻辑时钟、绝对截止及预算单位 |

**重跑。** 在仓库根目录调用 regression_runner/run.py，命令示例见 Ch38 第五节。三个候选名为 model-change、prompt-change、config-change；返回 1 是这些候选被暂缓。compare.py 读基线和候选，对齐切片并要求同一批输入；其退出码不用于发布。CI 应判断运行器退出码并保留 JSON。Ch37 原始探针用 `python examples/ch37/regression_probe.py --client buggy --output outputs/buggy-new`，对照为 fixed，每次选择新目录。

**主张与来源。** 业务结果和过程证据的区分见 [Anthropic 的 Agent 评估文章](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)。用已知反例核对测试的有效性和隔离环境参照 [Google SRE 的可靠性测试](https://sre.google/sre-book/testing-reliability/)、[故障实验原则](https://principlesofchaos.org/) 与 [pytest 临时目录](https://docs.pytest.org/en/stable/how-to/tmp_path.html)。重试应保持业务作用边界，参见 [RFC 9110 §9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)。独立观察使用 [SQLite URI](https://www.sqlite.org/uri.html) 的 mode=ro。跨服务追踪概念见 [OpenTelemetry Traces](https://opentelemetry.io/docs/concepts/signals/traces/) 及 [W3C Trace Context](https://www.w3.org/TR/trace-context/)。本地日志不是采集自这些平台的分布式 span。各切片原始成功与失败证据逐项见报告 rows，阈值见 golden_slices.yaml 和 trace_assertions.yaml。

**范围。** 配额与断连为本地适配器/引擎注入，after_commit 模拟客户端停止并重新打开数据库连接；未验证真实服务配额、网络和集群故障。模型与提示变更为确定性替身的受控实验，不能估计真实模型能力。完整线上容量、实际身份系统、独立审稿和人工例外审批另需记录。
