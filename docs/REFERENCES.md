# 参考来源

## 判断范式与服务

- [TypeSafe官方文档](https://docs.typesafe.ai/introduction)：官方服务与System One判断范式。当前已实测版本为jev-1.13.0，具体协议及模型以官方文档与实际响应为准。
- [XiaokeAILabs社区实现](https://github.com/li-xiu-qi/XiaokeAILabs/tree/main/experiments/test_jev_open_source/text_jev_train)：社区Jev-like模型参考，代码来源与本地修改见`demo/vendor/agentjev/NOTICE.md`。
- [mu](https://github.com/qybaihe/mu)：判断服务、策略及台账分离的参考，核查固定提交47c51b0c68f622e9953b7f501d165fe474eec588。本项目为独立Python实现。
- [腾讯技术工程相关文章](https://mp.weixin.qq.com/s/D1La4jMoVZ5Ip_RrVY1kPw)：用于理解结构化判断及快慢协同。仓库图表为项目场景设计，不把文章通用结果改写为本项目实测。

## 银行业务与政策

工行公开来源记录位于`docs/sources/工行公开来源.json`，政策与行业材料链接位于`docs/sources/policy-source-manifest.json`。链接与来源支持行业背景和生态适配讨论，不单独证明工小审的具体能力缺口。

最新计划书保留作者稿中的引用与脚注；同任务实验的来源hash和协议分别留存在实验目录。第三方全文、模型权重及他人完整仓库不随本项目再次打包。
