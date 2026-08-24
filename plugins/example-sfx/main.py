# -*- coding: utf-8 -*-
"""
example-sfx —— 示例插件：把 helminth engines/sfx_crawler.py 包装为独立插件。

独立更新说明：本目录只含 manifest.json + 本入口；实现可指向任意来源
（helminth 引擎 / 独立重写），hub 只按 manifest.entry 以子进程启动。
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_HELMINTH_ROOT = os.path.dirname(_HERE)
if _HELMINTH_ROOT not in sys.path:
    sys.path.insert(0, _HELMINTH_ROOT)


def main() -> None:
    try:
        from engines.sfx_crawler import SFXCrawlerEngine
        engine = SFXCrawlerEngine()
        print(f"[sfx-crawler] 引擎就绪: {engine.name}")
        print("[sfx-crawler] discover 示例（不实际下载）：")
        links = engine.discover(max_items=3)
        print(f"  发现 {len(links)} 条链接")
        for link in links[:3]:
            print(f"    {link}")
    except Exception as exc:  # 环境缺依赖时给出清晰提示（独立更新）
        print(f"[sfx-crawler] 启动失败: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
