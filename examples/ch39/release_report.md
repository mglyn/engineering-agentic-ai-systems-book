# 本地受控发布记录

使用仓库锁定的 Python 3.12 环境与第 36 章三项目执行入口。本轮四种配置各运行一次，使用新的本地目录。报告中的时间、测试输出和制品摘要可以随解释器、换行符或检出版本变化。

| 配置 | 退出码 | 报告 | 实际判断 |
| --- | ---: | --- | --- |
| 默认 | 0 | [五阶段记录](reports/normal.json) | 三项目、行为测试、十二切片通过。五阶段放行顺序为真、真、假、假、真 |
| skip-tests | 1 | [漏跑测试](reports/skip-tests.json) | tests 为假，未进入部署阶段 |
| log-marker | 1 | [日志标记](reports/log-marker.json) | log_marker_absent 为假，未进入部署阶段 |
| client-regression | 1 | [失败门禁交接](reports/client-regression.json) | 八个切片出现多余重发，regression 为假，未切换制品 |

在部分回滚阶段，程序判定观察员具有 read 和 approve，权威记录只有 read。原工单的操作身份、载荷、批准摘要和创建数贯穿五次采样均正确。恢复后的迟到告警来自第三阶段。生产授权为 false，人工复核待实际执行人填写。

命令与预期见第 39.5 节。正常路径保留 gate.json、projects 下全部三项目数据、build.log、两个可执行归档和 release.json，公开目录只收录可核对结论的报告。原始输入均为仓库的合成夹具。
