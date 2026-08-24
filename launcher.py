#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crawl_hub - 爬虫类工具统一启动器（聚合式，零耦合）

设计原则（吸取 helminth 融合式整合失败的教训）：
- 启动器只负责「展示 + 启动 + 停止」，不 import 任何爬虫工具的逻辑
- 每个工具以独立子进程 subprocess 启动，崩一个不影响其他，互不可见
- 工具清单配置驱动（crawlers.json），新增/移除工具只改 json，不动本文件
- path/entry 一律绝对路径，杜绝相对路径 bug

纪律升级（2026-08-23，借鉴 harness 的"配置即声明、启动即审计、运行即断言"）：
- 配置校验：启动即校验每个条目（字段/路径/入口/python 解释器），
  问题条目在面板上标注原因并禁用（fail-loud），--check 模式可无 GUI 审计；
- 任务事件日志：启动/退出/停止/错误全部追加写 data/tasks.log（JSONL，
  与 WorldLog 同构：seq/ts/type/payload），--dump-tasks 供 agent 审计。

用法：
    python launcher.py                  # GUI
    python launcher.py --check [--json] # 无 GUI 配置审计（exit 0=全部通过）
    python launcher.py --dump-tasks [--limit N] [--json]
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

_ROOT = os.path.dirname(os.path.abspath(__file__))
_CONFIG = os.path.join(_ROOT, "crawlers.json")
_TASKS_LOG = os.path.join(_ROOT, "data", "tasks.log")

REQUIRED_FIELDS = ("name", "category", "path", "entry")


# ─────────────────────────────────────────────────────────────
#  配置校验（启动审计）
# ─────────────────────────────────────────────────────────────

def validate_config(cfg: dict) -> list:
    """校验工具清单，返回问题列表 [{tool, problem}]（空列表=全部通过）。"""
    problems = []
    crawlers = cfg.get("crawlers", [])
    if not isinstance(crawlers, list) or not crawlers:
        problems.append({"tool": "(清单)", "problem": "crawlers 为空或不是数组"})
        return problems
    seen_names = set()
    for i, item in enumerate(crawlers):
        name = str(item.get("name", "")).strip() or f"第 {i + 1} 条"
        for field in REQUIRED_FIELDS:
            if not str(item.get(field, "")).strip():
                problems.append({"tool": name, "problem": f"缺少字段 '{field}'"})
                continue
        if item.get("name", "").strip() in seen_names:
            problems.append({"tool": name, "problem": f"工具名重复 '{item.get('name')}'"})
        seen_names.add(item.get("name", "").strip())
        path = str(item.get("path", "")).strip()
        entry = str(item.get("entry", "")).strip()
        if path and not os.path.isdir(path):
            problems.append({"tool": name, "problem": f"path 不存在: {path}"})
        elif path and entry and not os.path.isfile(os.path.join(path, entry)):
            problems.append({"tool": name, "problem": f"入口不存在: {os.path.join(path, entry)}"})
        py = str(item.get("python", "auto")).strip()
        if py and py != "auto" and not os.path.isfile(py):
            problems.append({"tool": name, "problem": f"python 解释器不存在: {py}"})
    return problems


# ─────────────────────────────────────────────────────────────
#  任务事件日志（JSONL，与 WorldLog 同构）
# ─────────────────────────────────────────────────────────────

class TaskLog:
    """追加式任务日志：data/tasks.log，条目 {seq, ts, type, tool, ...payload}。"""

    def __init__(self, path: str = _TASKS_LOG):
        self._path = path
        self._lock = threading.Lock()
        self._seq = 0

    def append(self, event_type: str, tool: str, **payload) -> dict:
        """追加一条任务事件，返回条目。"""
        with self._lock:
            if self._seq == 0:
                self._seq = self._read_max_seq()
            self._seq += 1
            entry = {"seq": self._seq, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "type": event_type, "tool": tool, **payload}
            try:
                os.makedirs(os.path.dirname(self._path), exist_ok=True)
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError:
                pass  # 日志失败不影响启动器功能
            return entry

    def _read_max_seq(self) -> int:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                seq = 0
                for line in f:
                    try:
                        seq = max(seq, int(json.loads(line).get("seq", 0)))
                    except (ValueError, json.JSONDecodeError):
                        continue
                return seq
        except OSError:
            return 0

    def read(self, limit: int = 50) -> list:
        """读取最近 limit 条任务事件（agent 审计用）。"""
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            return []
        entries = []
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries


# ─────────────────────────────────────────────────────────────
#  无 GUI 审计 CLI（--check / --dump-tasks）
# ─────────────────────────────────────────────────────────────

def cmd_check(args) -> int:
    try:
        with open(_CONFIG, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        if args.json:
            print(json.dumps({"ok": False, "error": f"配置读取失败: {e}"}, ensure_ascii=False))
        else:
            print(f"[错误] 无法读取 {_CONFIG}: {e}")
        return 2
    problems = validate_config(cfg)
    tools = cfg.get("crawlers", [])

    # 插件注册表（crawler-plugin 规范）：混用模式——crawlers.json 独立工具 + plugins/ 插件目录
    from crawler_registry import validate_plugins
    plugin_report = validate_plugins(os.path.join(_ROOT, "plugins"))

    report = {
        "ok": len(problems) == 0 and plugin_report["ok"],
        "tools_total": len(tools),
        "tools_ok": len(tools) - len({p["tool"] for p in problems if p["tool"] != "(清单)"}),
        "problems": problems,
        "plugins": plugin_report["plugins"],
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"crawl_hub 配置审计：{report['tools_ok']}/{report['tools_total']} 工具通过")
        for p in problems:
            print(f"  [✗] {p['tool']}: {p['problem']}")
        print(f"插件注册表：{len(plugin_report['plugins'])} 个插件")
        for pl in plugin_report["plugins"]:
            if pl["problems"]:
                for prob in pl["problems"]:
                    print(f"  [✗] {pl['name']}: {prob}")
            else:
                print(f"  [✓] {pl['name']}")
        print("全部通过 ✅" if report["ok"] else "存在配置问题（GUI 中对应卡片将禁用并标注原因）")
    return 0 if report["ok"] else 1


def cmd_dump_tasks(args) -> int:
    log = TaskLog()
    entries = log.read(limit=args.limit)
    if args.json:
        print(json.dumps(entries, ensure_ascii=False, indent=2))
    else:
        print(f"最近 {len(entries)} 条任务事件（{_TASKS_LOG}）：")
        for e in entries:
            extra = " ".join(f"{k}={v}" for k, v in e.items()
                             if k not in ("seq", "ts", "type", "tool"))
            print(f"  #{e['seq']} {e['ts']} [{e['type']}] {e['tool']} {extra}")
    return 0


# ─────────────────────────────────────────────────────────────
#  GUI（行为与升级前一致，新增校验标注与任务日志落盘）
# ─────────────────────────────────────────────────────────────

class CrawlHub:
    def __init__(self, tasklog: TaskLog = None):
        import tkinter as tk
        from tkinter import ttk, scrolledtext, messagebox

        self.tk, self.ttk, self.scrolledtext, self.messagebox = tk, ttk, scrolledtext, messagebox
        self.tasklog = tasklog or TaskLog()
        self.root = tk.Tk()
        self.root.title("crawl_hub - 爬虫工具统一启动器")
        self.root.geometry("860x640")
        self.root.resizable(True, True)

        self._procs = {}        # name -> subprocess.Popen
        self._start_ts = {}     # name -> 启动时刻（算时长）

        self._build_ui()
        self._load_config()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ──
    def _build_ui(self):
        ttk = self.ttk
        hdr = ttk.Frame(self.root)
        hdr.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(hdr, text="🕷  crawl_hub  ·  爬虫工具统一启动器",
                  font=("Microsoft YaHei", 14, "bold")).pack(side="left")
        ttk.Label(hdr, text="聚合不融合 · 每个工具独立进程",
                  font=("Microsoft YaHei", 9)).pack(side="right", padx=(0, 4))

        canvas = self.tk.Canvas(self.root, highlightthickness=0)
        scroll = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        self._list = ttk.Frame(canvas)
        self._list.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._list, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="top", fill="both", expand=True, padx=10, pady=4)
        scroll.pack(side="right", fill="y")

        logf = ttk.LabelFrame(self.root, text="运行日志")
        logf.pack(fill="both", padx=10, pady=(4, 8), expand=False)
        self._log = self.scrolledtext.ScrolledText(logf, height=7, font=("Consolas", 9))
        self._log.pack(fill="both", padx=6, pady=4)

    def _load_config(self):
        try:
            with open(_CONFIG, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            self.messagebox.showerror("配置错误", f"无法读取 {_CONFIG}:\n{e}")
            return
        problems = {p["tool"]: p for p in validate_config(cfg)}
        for p in problems.values():
            self.tasklog.append("config_error", p["tool"], problem=p["problem"])
            self._log_msg(f"[配置问题] {p['tool']}: {p['problem']}")
        for item in cfg.get("crawlers", []):
            self._add_card(item, problems.get(str(item.get("name", "")).strip()))

    def _add_card(self, item, problem=None):
        ttk = self.ttk
        name = item.get("name", "?")
        cat = item.get("category", "其他")
        desc = item.get("desc", "")
        path = item.get("path", "")
        entry = item.get("entry", "")
        py = item.get("python", "auto")

        f = ttk.LabelFrame(self._list, text=f"【{cat}】{name}")
        f.pack(fill="x", padx=6, pady=4)

        ttk.Label(f, text=desc, wraplength=620, font=("Microsoft YaHei", 9)).pack(
            anchor="w", padx=8, pady=(4, 2))
        ttk.Label(f, text=f"路径：{path}\{entry}", font=("Consolas", 8),
                  foreground="#555").pack(anchor="w", padx=8)

        row = ttk.Frame(f)
        row.pack(anchor="e", padx=8, pady=(2, 6))

        btn_start = ttk.Button(row, text="▶ 启动", width=10,
                               command=lambda: self._start(name, path, entry, py, btn_start, lbl))
        btn_start.pack(side="left", padx=3)
        btn_stop = ttk.Button(row, text="■ 停止", width=10, state="disabled",
                              command=lambda: self._stop(name, btn_start, btn_stop, lbl))
        btn_stop.pack(side="left", padx=3)
        ttk.Button(row, text="📂 打开目录", width=12,
                   command=lambda: os.startfile(path) if os.path.isdir(path) else None).pack(side="left", padx=3)

        lbl = ttk.Label(row, text="● 空闲", foreground="#888")
        lbl.pack(side="left", padx=8)

        if problem:
            ttk.Label(f, text=f"⚠ {problem['problem']}", font=("Microsoft YaHei", 9),
                      foreground="#b00020", wraplength=620).pack(anchor="w", padx=8)
            btn_start.configure(state="disabled")
            lbl.configure(text="● 配置问题", foreground="#b00020")

        btn_start._peer = btn_stop
        btn_start._status = lbl
        btn_stop._status = lbl
        btn_stop._start_btn = btn_start

    # ── 行为 ──
    def _resolve_python(self, py):
        if py and py != "auto":
            return py
        return sys.executable

    def _start(self, name, path, entry, py, btn_start, lbl):
        if name in self._procs and self._procs[name].poll() is None:
            self._log_msg(f"[跳过] {name} 已在运行")
            return
        entry_path = os.path.join(path, entry)
        if not os.path.isfile(entry_path):
            self._log_msg(f"[错误] 入口不存在：{entry_path}")
            self.tasklog.append("error", name, problem=f"入口不存在: {entry_path}")
            self.messagebox.showerror("入口缺失", f"找不到：\n{entry_path}")
            return
        try:
            proc = subprocess.Popen(
                [self._resolve_python(py), entry],
                cwd=path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except Exception as e:
            self._log_msg(f"[错误] 启动 {name} 失败：{e}")
            self.tasklog.append("error", name, problem=str(e))
            return
        self._procs[name] = proc
        self._start_ts[name] = time.time()
        btn_start.configure(state="disabled")
        if hasattr(btn_start, "_peer"):
            btn_start._peer.configure(state="normal")
        lbl.configure(text=f"● 运行中 PID={proc.pid}", foreground="#1a7a1a")
        self._log_msg(f"[启动] {name}  PID={proc.pid}  ({path}\{entry})")
        self.tasklog.append("launch", name, pid=proc.pid, entry=f"{path}\{entry}")
        self._watch(proc, name, btn_start, lbl)

    def _watch(self, proc, name, btn_start, lbl):
        def _pump():
            try:
                for line in proc.stdout:
                    self._log_msg(f"[{name}] {line.rstrip()}")
            except Exception:
                pass
            finally:
                if proc.poll() is not None:
                    self.root.after(0, lambda: self._mark_stopped(name, btn_start, lbl, proc.returncode))
        t = threading.Thread(target=_pump, daemon=True)
        t.start()

    def _mark_stopped(self, name, btn_start, lbl, code):
        duration = round(time.time() - self._start_ts.get(name, time.time()), 1)
        btn_start.configure(state="normal")
        if hasattr(btn_start, "_peer"):
            btn_start._peer.configure(state="disabled")
        lbl.configure(text=f"● 空闲（上次退出码 {code}）", foreground="#888")
        self._log_msg(f"[退出] {name}  退出码={code}  时长={duration}s")
        self.tasklog.append("exit", name, pid=self._procs.get(name).pid if self._procs.get(name) else None,
                            exit_code=code, duration_s=duration)
        self._procs.pop(name, None)

    def _stop(self, name, btn_start, btn_stop, lbl):
        proc = self._procs.get(name)
        if proc and proc.poll() is None:
            proc.terminate()
            self._log_msg(f"[停止] 已发送终止信号：{name}")
            self.tasklog.append("stop", name, pid=proc.pid)
            lbl.configure(text="● 终止中…", foreground="#b8860b")
        btn_stop.configure(state="disabled")

    def _log_msg(self, msg):
        self._log.insert("end", msg + "\n")
        self._log.see("end")

    def _on_close(self):
        running = [n for n, p in self._procs.items() if p.poll() is None]
        if running:
            if not self.messagebox.askokcancel("退出确认",
                                               f"仍有 {len(running)} 个工具在运行：\n{', '.join(running)}\n退出将一并终止，确定？"):
                return
            for p in self._procs.values():
                if p.poll() is None:
                    try:
                        p.terminate()
                    except Exception:
                        pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(prog="launcher.py", description="crawl_hub 爬虫工具统一启动器")
    parser.add_argument("--check", action="store_true", help="无 GUI 配置审计")
    parser.add_argument("--dump-tasks", action="store_true", help="输出任务事件日志")
    parser.add_argument("--limit", type=int, default=50, help="--dump-tasks 显示条数")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args(argv)
    if args.check:
        return cmd_check(args)
    if args.dump_tasks:
        return cmd_dump_tasks(args)
    CrawlHub().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
