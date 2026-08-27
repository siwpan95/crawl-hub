# 编排 harness 契约 spec（crawl-hub）

> 对齐 E:\lab port_spec.txt 思路：本文件是 harness 用例的单一真相来源；实现与 spec 冲突时以 spec 为准。

## 协议

- 行分隔 JSON（JSON-lines）：请求 {id, cmd, ...}；响应 {id, ok, value, error}；启动先回 {ready:true}。
- 逐请求超时：manifest timeout（crawl-gate 120s）。
- 生命周期：python 子进程由 port.mjs 登记 effect，harness 退出/dispose 时 kill（可逆效应）；stderr 抽干防死锁。

## cmd 集

| cmd | 语义 | 黄金值 |
|---|---|---|
| check | launcher.py --check --json：crawlers.json 7 工具 + plugins/ 插件注册表审计，value = problems 总数 | 0 |
| tasks | launcher.py --dump-tasks --json：任务事件日志条目数（JSONL 同构 WorldLog） | 无（informational，随运行增长） |

## 纪律

- 无新增端口；爬虫工具自身端口若存在，登记见 G:\docs\md\allin主工作区\ports.yaml / 端口分配表.md。
- crawlers.json 内 path/entry 一律绝对路径（2026-08-27 已随顶层目录拆分更新为 G:\\repos / G:\\assets）。
- 运行：node harness/harness.mjs；全绿 exit 0，任何分歧/报错 exit 1。

## E4/E5（2026-08-27 补）

- E4 eval-invariant：expectConsensus:true 的用例出现任何分歧/报错/失配 = 真失败（exit 1）；informational 用例（expected:null）可声明 expectDiverged 名单，超出预期分歧同样失败。
- E5 分歧事件订阅链路：分歧/报错事件以 JSON-lines 追加到 data/divergence-events.jsonl（可用 DIVERGENCE_EVENT_FILE 环境变量改路径），每条含 ts/case/consensus/expected/expectDiverged/diverged/errors/components（registry snapshot 健康快照），供 CI/上层订阅与告警。
| plugin-audit | crawl-gate | B 模式插件 manifest 审计（plugin:true 条目必填字段）+ crawler-kit 导入冒烟（引用不融合） | 0 |
| photo-smoke | crawl-gate | 真实网络冒烟（在线分层）：CRAWL_SMOKE=1 时用 image-scraper photo 源抓取 python.org 并统计图片 URL（>=1 通过）；未设置时返回 skipped，不纳入离线门禁 | 无（informational） |
