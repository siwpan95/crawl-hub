# -*- coding: utf-8 -*-
"""
crawler_registry.py —— 爬虫插件注册表扫描/校验原型（纯标准库，无第三方依赖）

职责（hub 只装配，不 import 插件逻辑）：
  - 扫描根目录下各插件目录的 manifest.json
  - 校验必填字段 + 端口登记检查（port 字段必须在端口分配表出现过）
  - --check 无 GUI 审计（exit 0=全部通过），供 agent/CI 使用
  - 任务日志（JSONL，与 WorldLog 同构）留待 hub 启动/停止时写入

用法：
    python crawler_registry.py --check --root <插件根目录> [--json]
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

REQUIRED = ("name", "version", "entry", "interface")
# 端口分配表登记值（随表更新；表是唯一事实源）
REGISTERED_PORTS = {"8000", "8010", "8080", "8100", "8554", "8888", "8889", "8899", "9000", "9997"}


def scan_plugins(root: str) -> list:
    """扫描 root 下含 manifest.json 的插件目录，返回 [(目录, manifest)]。"""
    found = []
    base = Path(root)
    if not base.is_dir():
        return found
    for d in sorted(base.iterdir()):
        if not d.is_dir() or d.name.startswith((".", "_")):
            continue
        mf = d / "manifest.json"
        if mf.is_file():
            try:
                found.append((str(d), json.loads(mf.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError):
                found.append((str(d), None))
    return found


def validate_plugins(root: str) -> dict:
    """校验全部插件，返回 {ok, plugins: [{dir, name, problems[]}]}。"""
    plugins = []
    ok = True
    for d, mf in scan_plugins(root):
        problems = []
        if mf is None:
            problems.append("manifest.json 无法解析")
        else:
            for field in REQUIRED:
                if not str(mf.get(field, "")).strip():
                    problems.append(f"缺少字段 '{field}'")
            port = str(mf.get("port", "")).strip()
            if port and port not in REGISTERED_PORTS:
                problems.append(f"端口 {port} 未登记（先查 G:\allin\docs\md\allin主工作区\端口分配表.md）")
        if problems:
            ok = False
        plugins.append({"dir": d, "name": (mf or {}).get("name", os.path.basename(d)), "problems": problems})
    return {"ok": ok, "plugins": plugins}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="crawler_registry.py", description="爬虫插件注册表扫描/校验")
    parser.add_argument("--check", action="store_true", help="无 GUI 审计")
    parser.add_argument("--root", default=os.path.dirname(os.path.abspath(__file__)), help="插件根目录")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args(argv)
    report = validate_plugins(args.root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    print(f"插件注册表审计：{len(report['plugins'])} 个插件")
    for p in report["plugins"]:
        if p["problems"]:
            for prob in p["problems"]:
                print(f"  [✗] {p['name']}: {prob}")
        else:
            print(f"  [✓] {p['name']}")
    print("全部通过" if report["ok"] else "存在插件问题")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
