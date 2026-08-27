# driver.py — harness 侧适配器（对应 E:\lab chess-cordis/drivers/py/py_engine_driver.py）：
# 把仓内真实入口（launcher.py 无 GUI 审计 CLI）包装成 JSON-lines 协议。
# 引擎零胶水原则：launcher.py 不知道 harness 存在；本文件是唯一胶水。
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = os.environ.get("CRAWL_PYTHON") or r"F:\Python314\python.exe"


def _run(args, timeout):
    return subprocess.run([PYTHON, "launcher.py", *args], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8",
                          timeout=timeout)


def cmd_check(_payload):
    try:
        r = _run(["--check", "--json"], timeout=60)
        report = json.loads(r.stdout or "{}")
    except Exception as e:
        return {"ok": False, "value": None, "error": "check failed: " + str(e)}
    problems = len(report.get("problems") or [])
    problems += sum(len(p.get("problems") or []) for p in (report.get("plugins") or []))
    ok = r.returncode == 0 and report.get("ok") is True
    return {"ok": ok, "value": problems if ok else None,
            "error": None if ok else ((r.stderr or r.stdout or "")[-800:])}


def cmd_plugin_audit(_payload):
    try:
        r = _run(["--plugin-audit", "--json"], timeout=60)
        report = json.loads(r.stdout or "{}")
    except Exception as e:
        return {"ok": False, "value": None, "error": "plugin-audit failed: " + str(e)}
    problems = len(report.get("problems") or [])
    ok = r.returncode == 0 and report.get("ok") is True
    return {"ok": ok, "value": problems if ok else None,
            "error": None if ok else ((r.stderr or r.stdout or "")[-800:])}


def cmd_smoke(_payload):
    # 在线冒烟分层：仅 CRAWL_SMOKE=1 时真实联网；离线黄金值门禁保持绿
    if not os.environ.get("CRAWL_SMOKE"):
        return {"ok": True, "value": "skipped"}
    try:
        r = _run(["--smoke", "photo", "--json"], timeout=90)
        report = json.loads(r.stdout or "{}")
    except Exception as e:
        return {"ok": False, "value": None, "error": "smoke failed: " + str(e)}
    ok = r.returncode == 0 and report.get("ok") is True
    return {"ok": ok, "value": report.get("urls") if ok else None,
            "error": None if ok else ((r.stderr or r.stdout or "")[-600:])}


def cmd_tasks(_payload):
    try:
        r = _run(["--dump-tasks", "--json"], timeout=30)
        txt = (r.stdout or "").strip()
        data = json.loads(txt) if txt else []
        n = len(data) if isinstance(data, list) else 1
    except Exception as e:
        return {"ok": False, "value": None, "error": "tasks failed: " + str(e)}
    return {"ok": r.returncode == 0, "value": n,
            "error": None if r.returncode == 0 else ((r.stderr or "")[-400:])}


CMDS = {"check": cmd_check, "tasks": cmd_tasks, "plugin-audit": cmd_plugin_audit, "smoke": cmd_smoke}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        fn = CMDS.get(req.get("cmd"))
        if fn:
            resp = {"id": req.get("id"), **fn(req)}
        else:
            resp = {"id": req.get("id"), "ok": False, "error": "unknown cmd: " + str(req.get("cmd"))}
        print(json.dumps(resp, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
