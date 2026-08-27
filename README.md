# crawl_hub - 爬虫类工具统一启动器

聚合式整合（aggregation，非融合 fusion）。吸取 `helminth` 融合式整合失败的教训：
把 webcopier / sfx / font / bilibili / image-scraper 等爬虫**重写融合**成一个框架，
结果三原工具一个没退役、反而更活跃，等于 4 份副本、整合框架被冷落。

本启动器只做一件事：**统一入口 + 独立启动**，不碰任何工具逻辑。

## 原则

- 启动器只负责「展示 + 启动 + 停止」，**不 import 任何爬虫工具**
- 每个工具以**独立子进程**启动，崩一个不影响其他，互不可见（零耦合）
- 工具清单配置驱动（`crawlers.json`），新增/移除工具只改 json
- `path` / `entry` 一律**绝对路径**，杜绝相对路径 bug

## 用法

```bash
python launcher.py                      # GUI 启动器
python launcher.py --check [--json]     # 无 GUI 配置审计（exit 0=全部通过）
python launcher.py --dump-tasks [--limit N] [--json]   # 任务事件日志审计
```

点击工具卡片的「▶ 启动」即以其自身目录为 cwd 拉起该工具的 GUI；
「■ 停止」发送终止信号；「📂 打开目录」在资源管理器打开该工具目录。
底部日志实时显示各工具的 stdout / 退出事件。

## 纪律升级（2026-08-23）

- **配置校验（启动审计）**：启动即校验每条工具（字段/路径/入口/python 解释器），
  有问题的卡片禁用并在卡片上标注原因（fail-loud）；
  `--check` 可无 GUI 一键审计全部工具路径。
- **任务事件日志**：启动/退出/停止/错误全部追加写 `data/tasks.log`（JSONL，
  与 WorldLog 同构：seq/ts/type/tool/...），`--dump-tasks` 供 agent 审计。
- 聚合原则不变：工具仍是独立子进程，不 import、不融合。

## 插件注册表（crawler-plugin 规范，2026-08-24 移入）

- 规范：`PLUGIN_SPEC.md`（每个爬虫 = 一个插件目录 + manifest.json，独立更新）；
- 扫描/校验：`crawler_registry.py`——必填字段 + **端口登记检查**（port 必须先查端口分配表）；
- 混用模式：`--check` 同时审计 crawlers.json 工具与 `plugins/` 插件目录（示例：`plugins/example-sfx`，源自 helminth 引擎包装）；
- 任务日志（data/tasks.log）与 WorldLog 同构，插件进程启动/退出同样入日志。

## crawlers.json 字段

| 字段 | 说明 |
|---|---|
| `name` | 显示名 |
| `category` | 分组（网页/图片/音效/字体/视频） |
| `path` | 工具目录（绝对路径） |
| `entry` | 入口脚本（相对于 path） |
| `desc` | 描述 |
| `python` | `auto` = 启动器解释器；或填某工具 venv 的 python 绝对路径 |

## 已聚合工具

- 网页：webcopier
- 图片：image-scraper、photo
- 音效：sfx
- 字体：font_downloader2（网络）、font_downloader（本地，与网络版互补）
- 视频：bilibili-helper-py

> 注：`right/helminth` 是之前失败的融合式整合副本，可移入隔离区；
> `right/video_generator/sfx` 是 video_generator 的内嵌音效模块（库，非独立工具），不在此收编。

---

## 编排 harness（离线黄金值门禁）

`node harness/harness.mjs`——组件清单 harness/manifest.json，契约 harness/spec.md：

- config-audit：launcher.py --check --json（crawlers.json 7 工具 + plugins/ 插件注册表）→ 黄金值 problems 总数 0
- task-log：launcher.py --dump-tasks --json 条目数（informational，随运行增长）

JSON-lines 子进程协议（python 驱动，对应 E:\lab chess-cordis/drivers/py/py_engine_driver.py）+ ready 握手 + 逐请求超时；子进程由 port 层登记 effect，退出即 kill；全绿 exit 0，任何分歧/报错 exit 1。无新增端口。
