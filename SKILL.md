---
name: crawl-hub
description: Maintain the crawl_hub crawler launcher (G:/crawlers/crawl_hub). Aggregation-not-fusion launcher with config audit and JSONL task log.
agent_created: true
---

# crawl_hub 爬虫聚合启动器维护

## 核心原则（不可破坏）
- 聚合不融合：启动器只负责展示+启动+停止，**绝不 import 任何爬虫工具逻辑**（helminth 融合失败的教训）
- 工具一律独立子进程（CREATE_NEW_CONSOLE），崩一个不影响其他
- 新增/移除工具只改 crawlers.json（绝对路径 + python 字段），不动 launcher.py

## 结构
- launcher.py：GUI + validate_config 启动审计 + TaskLog + --check/--plugin-audit/--smoke/--dump-tasks CLI
- crawlers.json：10 个工具清单（webcopier/image-scraper/photo/sfx/fonts×2/bilibili/midjourney-video/sign-in/novel-down）
- B 模式插件（plugin:true + 工具仓 manifest.json，6 个）：webcopier、image-scraper、bilibili-helper-py、midjourney_video、sign-in-simulator、novel-down
- data/tasks.log：JSONL 任务事件（launch/exit/stop/error/config_error）
- tests/test_hub.py：pytest 9/9
- harness/：manifest.json（组件清单）+ port.mjs（JSON-lines 子进程端口）+ driver.py + harness.mjs（黄金值跑批）

## 常用命令
- 审计：python launcher.py --check [--json]（exit 0=全过）
- 插件审计：python launcher.py --plugin-audit [--json]（manifest 必填字段 + crawler-kit 导入）
- 任务日志：python launcher.py --dump-tasks [--limit N] [--json]
- 黄金值：node harness/harness.mjs（全绿 exit 0）
- 测试：python -m pytest tests -q

## 已知陷阱
- 路径必须绝对路径；工具搬家后要同步 crawlers.json（曾有 D:/allin 旧路径残留）
- GBK 控制台：main() 已 reconfigure utf-8，勿删
- 工具入口缺失时卡片禁用并标注原因（fail-loud），不要静默跳过
- **入口必须是「工具目录下的文件」**（launcher 校验 `os.path.isfile(path\entry)`，启动方式 `python <entry>`，cwd=工具目录）；
  若工具本体是**包模块入口**（`python -m pkg.gui`，内部用相对导入），要在**工具仓自己**加一个薄壳文件
  （先例：novel-down 的 `run_gui.py` = 塞仓根进 sys.path 后转交 `noveldown.gui.main`），
  不要在 launcher.py 里特判——聚合不融合，改动留在各自仓内
