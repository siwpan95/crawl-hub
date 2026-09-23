# Changelog

本项目所有值得注意的变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### Added

- 接入 **novel-down（读书爬虫，仅免费章节）**：crawlers.json 第 10 个工具、`category: 小说`、`plugin: true`；
  其仓内新增 `manifest.json`（interface: discover/fetch/extract/transform）与文件级入口薄壳 `run_gui.py`
  （GUI 本体是包模块 `noveldown.gui`，而 launcher 的 entry 约定是「工具目录下的文件」）。
  注：novel-down 未 import `crawler-kit`，故 manifest **不声明** `kit` 依赖（避免 2026-08-27 复盘指出的「虚标 kit」）。
- harness/spec.md 的 cmd 集补上 plugin-audit / photo-smoke 两行（此前误落在 E4/E5 段之后，表格不完整）。
- **依赖探测（`--check` 新增）**：crawlers.json 支持可选字段 `requires`（该工具核心第三方依赖，**写 import 名**），
  `--check` 会按每条目**解析出的解释器**（`auto` = 启动器解释器）逐一 `importlib.util.find_spec` 探测，缺失即报问题。
  动机：`python: auto` 跟随启动器解释器，换解释器时会出现「卡片能起、抓取缺依赖」的静默降级——现在在审计阶段就暴露。
  已为 6 个 B 模式插件声明核心依赖：webcopier/novel-down `["requests","bs4"]`、image-scraper/midjourney_video `["httpx"]`、
  bilibili-helper-py `["requests","yt_dlp"]`、sign-in-simulator `["pandas"]`（依据各仓 requirements.txt 实测）。
- **「插件数」两处口径写进文档**：`plugins/` 目录型注册表当前 1 个（example-sfx）；B 模式真实接入 6 个；crawlers.json 工具 10 条。

### Changed

- 文档同步工具数：crawlers.json 7 → 10（README 已聚合工具清单、SKILL.md 结构与陷阱、harness/spec.md）。

### Fixed

- launcher.py 三处 f-string 里的 `\{entry}`（非法转义，Python 3.14 起每次运行打 SyntaxWarning、提示未来会失效）
  改为 `{path}{os.sep}{entry}`（Windows 下输出与原先逐字一致，行为不变）。

## [1.0.0] - 2026-08-27

### Added

- 首个发行版：便携源码 zip（剔除 .venv/构建产物/输出物，依赖见 README）。
- 发布面：gitee [siwpan/crawl-hub](https://gitee.com/siwpan/crawl-hub) release `v1.0.0`（爬虫聚合启动器 v1.0.0）。