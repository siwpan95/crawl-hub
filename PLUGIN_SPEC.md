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
