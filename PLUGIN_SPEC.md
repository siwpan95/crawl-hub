# crawler-plugin 插件规范 v1（草案，helminth 复活样板）

> 2026-08-24 制定。原则：**每个爬虫 = 一个插件，独立更新；hub 只装配/启动/审计，不 import 插件逻辑（子进程隔离）；统一端口（若有服务）从端口分配表读取。**

## 插件形态

一个插件 = 一个目录：

```
crawler-plugin/
├── manifest.json     # 插件清单（见下）
└── <任意实现文件>     # 插件自己的代码，独立更新
```

## manifest.json 字段

| 字段 | 必填 | 说明 |
|---|---|---|
| name | ✅ | 插件唯一名（如 sfx-crawler） |
| version | ✅ | 语义化版本（独立更新标识） |
| entry | ✅ | 入口命令（子进程启动：如 `python -m plugin.main`） |
| interface | ✅ | 能力接口声明：discover / download（对应 helminth BaseEngine 接口） |
| description | 可选 | 一句话说明 |
| port | 可选 | 若插件自带 Web/API 服务，端口必须**先查端口分配表再填** |
| config | 可选 | 配置 schema 提示（键值说明） |
| python | 可选 | 解释器（默认 auto=宿主解释器） |

## 纪律

1. **独立更新**：插件目录自包含；升级 = 替换目录或改 version，不动 hub 与其他插件；
2. **子进程隔离**：hub 以 `subprocess` 启动 entry，崩一个不影响其他（helminth 教训）；
3. **统一端口**：port 字段必须登记于 G:\docs\md\allin主工作区\端口分配表.md；
4. **任务日志**：hub 记录 JSONL（launch/exit/exit_code/duration），与 WorldLog 同构；
5. **共享运行时库**（可选）：反爬核心（身份轮换/限速/下载器）由 helminth core/ 提炼为独立库供插件引用，但**引用不融合**——库有版本，插件声明依赖版本。

## 与现有组件的关系

- crawl_hub（聚合启动器）：进程级 hub 已具备——其 crawlers.json 升级为插件注册表（扫描各插件目录 manifest.json）；
- helminth core/（反爬运行时）：提炼为 `crawler-kit` 库，供插件 import；
- helminth engines/（font/sfx/web）：转型为**三个独立插件**（各自目录 + manifest），原 sources/ JSON 随各自插件走。

## 示例插件（本目录 example-sfx/）

把 helminth 的 sfx 引擎包装为独立插件：manifest.json 声明 interface/entry，运行由宿主启动。

## v2 增补（2026-08-27 爬虫插件化规划 P1）

> 决策：爬虫类适合插件化（用户拍板）；先规范后改造。本增补与 v1 共存，v2 项目照此执行。

### manifest 新增字段

| 字段 | 必填 | 说明 |
|---|---|---|
| stop | 可选 | **停止命令（dispose 纪律，对齐 allin-platform）**：有优雅停止脚本必须声明（如 stop.bat / 信号处理入口）；缺省 = 宿主按 PID 树杀；任务日志记录 stop-graceful / stop-force / stop 三类动作 |
| interface | ✅ | v1 的 discover/download 之外，允许 etch（列表页拉取）/ extract（正文抽取）/ 	ransform（转码）——与 image-scraper A 模式的 fetch_tasks/download 对齐 |

### 形态选型表（A 进程内 / B 进程级 / C 迁移）

| 条件 | 形态 | 样板 |
|---|---|---|
| 同语言轻量、源族多、需共享状态（断点/进度/代理池/身份池） | **A 进程内插件**：源 = 注册表条目（JSON 配置 + 一个模块） | image-scraper（16 源，新源 ≈30 行） |
| 重依赖/易崩/跨语言/独立发布/自带 GUI 或服务 | **B 进程级插件**：manifest + 子进程隔离 | crawl-hub 本规范（webcopier 为首个接入） |
| 已有浏览器扩展/网页形态的能力 | **C 迁移**：契约先定、宿主可换（Playwright 桥接） | bilibili-helper-py（Chrome 扩展 → 桌面应用） |
| 单站点一次性脚本、无人维护 | 归档/单体，不插件化 | notpython 老爬虫四件（2026-08-27 已归档） |

### 共享运行时库（纪律 5 升级）

- crawler-kit 三件全提（用户拍板）：**Downloader**（限速/重试/断点续传/防盗链，自 image-scraper）+ **身份池**（UA/代理轮换，自 webcopier）+ **登录态**（Playwright 登录态管理，自 bilibili-helper-py）。
- 引用不融合：插件在 manifest 里声明 kit: { downloader: ^1, identity: ^1, session: ^1 }；库有版本，插件声明依赖版本。
