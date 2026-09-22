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

### Changed

- 文档同步工具数：crawlers.json 7 → 10（README 已聚合工具清单、SKILL.md 结构与陷阱、harness/spec.md）。

### Fixed

- launcher.py 三处 f-string 里的 `\{entry}`（非法转义，Python 3.14 起每次运行打 SyntaxWarning、提示未来会失效）
  改为 `{path}{os.sep}{entry}`（Windows 下输出与原先逐字一致，行为不变）。

## [1.0.0] - 2026-08-27

### Added

- 首个发行版：便携源码 zip（剔除 .venv/构建产物/输出物，依赖见 README）。
- 发布面：gitee [siwpan/crawl-hub](https://gitee.com/siwpan/crawl-hub) release `v1.0.0`（爬虫聚合启动器 v1.0.0）。