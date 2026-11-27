# Exp-25-01　多模态引用与媒体同步

使用 CPython 3.12 标准库。从仓库根目录运行：

```shell
python examples/ch25/media_sync.py
python examples/ch25/playout.py
```

Windows CPython 3.12.16 的两份输出归档在 reports/。第一份每行决策包含期望、实际编号、使用的轮次、来源版本、虚拟时钟决策时刻和理由。第二份给出 20 个片段、两种缓冲、每片段六个虚拟对齐点，共 240 行。每个条件一次，全部输入固定，无随机采样或性能外推。

原创输入包括 20 句中文与 20 张 SVG 虚拟票据，不含真实业务单据或个人影像。对应 WAV 为本地 Microsoft Huihui Desktop 对这些原创语句的合成朗读，不含用户语音或语音引擎文件。素材供本书教学实验使用。运行时直接读取已归档的文件，不需要 Windows 语音接口、联网、ASR 或视觉模型。生成脚本 make_cases.py 构造图、事件与人工设定的业务期望；render_speech.ps1 供安装相同中文语音的 Windows 环境重新朗读。模型输出标注是教学夹具；声音中的实际词边界没有对齐到虚拟时钟。

协议输入限单会话，调用方按会话分流；只解释当前已声明的 turn。每条定稿使用显式 ref 和方向，图片／文件则提供同一引用下的对象表。对话样例没有真实麦克风、在线文件上传、身份认证或姿态传感器。等待窗口模拟事件发生到达差，不能替代设备端时延测量。参见 degradation_matrix.md 的逐情形期望。

| 主张 | 资料或证据 |
| --- | --- |
| 媒体时钟需有共同参考 | [RTP §5.1、§6.4.1](https://www.rfc-editor.org/rfc/rfc3550)；[High Resolution Time](https://www.w3.org/TR/hr-time-3/) 的单调时钟与时间源 |
| 字幕 cue 与媒体时间的关联 | [WebVTT](https://www.w3.org/TR/webvtt1/) 的 cue timings；本章实验只模拟播放点 |
| 来源和指针坐标各有语义 | [Media Capture and Streams](https://www.w3.org/TR/mediacapture-streams/) 关于 track/source；[Pointer Events](https://www.w3.org/TR/pointerevents3/) 关于指针事件属性 |
| 轮次检测、插话与误打断的取舍 | [LiveKit 官方说明](https://docs.livekit.io/agents/logic/turns/)；输出侧的代次失效另见 Ch24 |
| 将媒体接到工单时旧图可能改变目标 | 归档 media.json 的 previous_turn 和 old_transcript。对象正确、轮次正确和降级正确分别验收 |
| 缓冲改变模拟同步误差和首段等待 | 归档 playout.json；按同一 cue 的 text_on、audio_on 计算偏差。音视频起点由教学设计给定 |

独立增量是有左右编号的原创素材、带页面版本的故障时序、两种关联策略、两种虚拟缓冲策略及可复查的原始结果。团队独立复核与真设备测量尚待执行。
