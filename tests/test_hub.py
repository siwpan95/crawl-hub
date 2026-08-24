"""
crawl_hub 纪律升级行为测试
===========================
覆盖：配置校验（缺字段/路径失效/入口缺失/python 失效/重名）、
任务事件日志（JSONL 追加/顺序/读取）。
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from launcher import TaskLog, validate_config
from crawler_registry import validate_plugins


def _cfg(crawlers):
    return {"crawlers": crawlers}


def _ok_item(name="工具A", path="G:/tools", entry="x.py", **kw):
    item = {"name": name, "category": "测试", "path": path, "entry": entry,
            "desc": "", "python": "auto"}
    item.update(kw)
    return item


def test_validate_all_ok():
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "tool"))
        entry = os.path.join(tmp, "tool", "main.py")
        open(entry, "w").close()
        problems = validate_config(_cfg([_ok_item(path=os.path.join(tmp, "tool"), entry="main.py")]))
    assert problems == []


def test_validate_missing_field():
    problems = validate_config(_cfg([{"name": "缺字段", "category": "x", "path": "p"}]))
    assert any("缺少字段 'entry'" in p["problem"] for p in problems)


def test_validate_path_missing():
    problems = validate_config(_cfg([_ok_item(path="Z:/definitely/not/here")]))
    assert any("path 不存在" in p["problem"] for p in problems)


def test_validate_entry_missing():
    with tempfile.TemporaryDirectory() as tmp:
        problems = validate_config(_cfg([_ok_item(path=tmp, entry="nope.py")]))
    assert any("入口不存在" in p["problem"] for p in problems)


def test_validate_python_missing():
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "tool"))
        open(os.path.join(tmp, "tool", "main.py"), "w").close()
        problems = validate_config(_cfg([
            _ok_item(path=os.path.join(tmp, "tool"), entry="main.py", python="Z:/nope/python.exe")]))
    assert any("解释器不存在" in p["problem"] for p in problems)


def test_validate_duplicate_names():
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "tool"))
        open(os.path.join(tmp, "tool", "main.py"), "w").close()
        problems = validate_config(_cfg([
            _ok_item(name="重复", path=os.path.join(tmp, "tool"), entry="main.py"),
            _ok_item(name="重复", path=os.path.join(tmp, "tool"), entry="main.py"),
        ]))
    assert any("重复" in p["problem"] for p in problems)


def test_validate_empty_list():
    problems = validate_config(_cfg([]))
    assert any("为空" in p["problem"] for p in problems)


def test_tasklog_append_and_read():
    with tempfile.TemporaryDirectory() as tmp:
        log = TaskLog(os.path.join(tmp, "tasks.log"))
        log.append("launch", "工具A", pid=123)
        log.append("exit", "工具A", pid=123, exit_code=0, duration_s=1.5)
        entries = log.read()
    assert len(entries) == 2
    assert entries[0]["type"] == "launch" and entries[0]["seq"] == 1
    assert entries[1]["type"] == "exit" and entries[1]["exit_code"] == 0


def test_tasklog_seq_continues_across_instances():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "tasks.log")
        TaskLog(path).append("launch", "A", pid=1)
        log2 = TaskLog(path)
        e = log2.append("exit", "A", exit_code=0)
        assert e["seq"] == 2


# ── 插件注册表（crawler-plugin 规范） ─────────────────

def test_registry_good_plugin():
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "good-plugin")
        os.makedirs(d)
        with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "good", "version": "1.0.0", "entry": "python -m good",
                       "interface": ["discover"]}, f)
        report = validate_plugins(tmp)
    assert report["ok"] is True
    assert report["plugins"][0]["name"] == "good"


def test_registry_unregistered_port_flagged():
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "bad-port")
        os.makedirs(d)
        with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "bad-port", "version": "1.0.0", "entry": "python -m bad",
                       "interface": ["discover"], "port": "7777"}, f)
        report = validate_plugins(tmp)
    assert report["ok"] is False
    assert any("未登记" in p for p in report["plugins"][0]["problems"])


def test_registry_missing_field():
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "incomplete")
        os.makedirs(d)
        with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "incomplete"}, f)
        report = validate_plugins(tmp)
    assert report["ok"] is False
    assert any("缺少字段" in p for p in report["plugins"][0]["problems"])
