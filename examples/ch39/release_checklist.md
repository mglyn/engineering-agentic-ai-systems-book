# PRJ-3 发布清单

| 时点 | 交接时必须能指出的材料 | 实验验收 |
| --- | --- | --- |
| 构建前 | Python 3.12、根 uv.lock、第 36 章 manifest、三档配置 | 从新目录开始 |
| 构建后 | r1.pyz、r2.pyz 与 release.json 内的制品摘要 | 现场所用字节能与记录对上 |
| 放入教学预发布前 | projects/reproduction.json、行为测试进程输出、gate.json | 三个项目复现成功、指定测试确实运行、十二项通过 |
| 输出日志前 | build.log、合成标记扫描结果 | 带标记的对照退出 1 |
| 受控发布后 | controlled-release 和 before 两行 | 工单、政策与权限满足同一组期望 |
| 交给下一组时 | release.json、失败对照、回滚手册、具名复核 | 记录复核者实际检查的范围与版本 |

实验维护者可批准在新的本地目录执行练习。共享预发布或正式环境由其所有者批准。课堂报告的 human_review 初始值始终为 pending。
