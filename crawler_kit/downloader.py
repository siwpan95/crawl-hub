# -*- coding: utf-8 -*-
"""
通用异步下载器（crawler_kit.downloader）

来源记账（借鉴必记账）：提炼自 G:\\repos\\image-scraper\\sources\\base.py 的
Downloader / ImageTask（2026-08-27 crawler-kit P3）。能力：
  - httpx 异步并发下载（semaphore 控制并发）
  - 速率限制（请求/秒）与速度限制（KB/s 流式节流）
  - 指数退避重试 + 格式回退（.png/.webp/.jpg/.jpeg 等）
  - 断点续传（已存在同名文件跳过）
  - Referer 防盗链（显式或从 URL 推导）
  - 失败清单收集（供重投）
依赖：httpx
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger("crawler_kit")

MEDIA_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".bmp",
              ".mp4", ".webm", ".mov", ".m4v",
              ".mp3", ".wav", ".ogg", ".m4a")


@dataclass
class Task:
    """单文件下载任务（跨插件统一结构，对应 image-scraper ImageTask）"""
    url: str = ""
    source: str = ""          # 插件/来源名
    title: str = ""
    author: str = ""
    local_path: str = ""
    downloaded: bool = False
    referer: str = ""          # 下载时用到的 Referer（绕过防盗链）
    meta: dict = field(default_factory=dict)


class Downloader:
    """通用异步下载器（httpx，支持代理、断点续传、格式回退、限速、重试）。"""

    def __init__(self, output_dir: Path, concurrency: int = 5, proxy: Optional[str] = None,
                 retries: int = 3, rate_limit: float = 0.0, speed_limit: float = 0.0):
        self.output_dir = Path(output_dir)
        self.concurrency = concurrency
        self.proxy = proxy
        self.retries = max(1, retries)
        self.rate_limit = rate_limit      # 请求/秒，0=不限
        self.speed_limit = speed_limit    # KB/s，0=不限
        self.downloaded: set = set()
        self.failed: list = []            # 失败清单（含 referer/meta，供重投）
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_lock = asyncio.Lock() if rate_limit > 0 else None
        self._last_call = 0.0
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._load_existing()

    # ── 断点续传 ──
    def _load_existing(self):
        for f in self.output_dir.iterdir():
            if f.is_file() and f.suffix.lower() in MEDIA_EXTS:
                self.downloaded.add(f.name)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                proxy=self.proxy,
                trust_env=False,
                limits=httpx.Limits(max_connections=self.concurrency + 5),
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                },
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── 批下载 ──
    async def download_batch(self, tasks: list) -> list:
        sem = asyncio.Semaphore(self.concurrency)
        stats = {"downloaded": 0, "skipped": 0, "errors": 0}

        async def one(t: Task) -> Task:
            async with sem:
                return await self._download(t, stats)

        results = await asyncio.gather(*[one(t) for t in tasks], return_exceptions=True)
        out = []
        for r in results:
            if isinstance(r, Task):
                out.append(r)
            else:
                stats["errors"] += 1
        return out

    async def _throttle_rate(self):
        if self._rate_lock is None:
            return
        async with self._rate_lock:
            gap = 1.0 / self.rate_limit
            now = time.monotonic()
            wait = self._last_call + gap - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()

    async def _download(self, task: Task, stats: dict) -> Task:
        fname = self._make_filename(task)
        if fname in self.downloaded:
            task.local_path = str(self.output_dir / fname)
            task.downloaded = True
            stats["skipped"] += 1
            return task

        client = self._get_client()
        referer = task.referer or self._derive_referer(task.url)
        content = None
        for attempt in range(1, self.retries + 1):
            await self._throttle_rate()
            content = await self._try(client, task.url, referer)
            if not content:
                for fb in self._fallbacks(task.url):
                    content = await self._try(client, fb, referer)
                    if content:
                        ext = Path(fb.split("?")[0]).suffix.lower()
                        if ext in MEDIA_EXTS:
                            base = fname.rsplit(".", 1)[0]
                            fname = base + ext
                        break
            if content:
                break
            if attempt < self.retries:
                backoff = min(2 ** attempt, 10)
                await asyncio.sleep(backoff)

        if content and len(content) > 300:
            fp = self.output_dir / fname
            fp.write_bytes(content)
            task.local_path = str(fp)
            task.downloaded = True
            self.downloaded.add(fname)
            stats["downloaded"] += 1
        else:
            stats["errors"] += 1
            self.failed.append({
                "url": task.url, "referer": referer, "source": task.source,
                "title": task.title, "author": task.author, "meta": task.meta,
            })
        return task

    async def _try(self, client: httpx.AsyncClient, url: str, referer: str = "") -> Optional[bytes]:
        try:
            headers = {"Referer": referer} if referer else {}
            if self.speed_limit > 0:
                buf = bytearray()
                bytes_per_sec = self.speed_limit * 1024.0
                async with client.stream("GET", url, headers=headers) as r:
                    if r.status_code != 200:
                        return None
                    async for chunk in r.aiter_bytes(64 * 1024):
                        buf.extend(chunk)
                        await asyncio.sleep(len(chunk) / bytes_per_sec)
                return bytes(buf) if len(buf) > 300 else None
            r = await client.get(url, headers=headers)
            if r.status_code == 200 and len(r.content) > 300:
                return r.content
            return None
        except Exception:
            return None

    # ── 文件名与 URL 工具（纯函数，测试友好）──
    def _make_filename(self, task: Task) -> str:
        h = hashlib.md5(task.url.encode()).hexdigest()[:12]
        ext = self._guess_ext(task.url)
        variant = ""
        if "?" in task.url:
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(task.url).query)
            if "w" in q or "h" in q:
                variant = "_" + q.get("w", ["0"])[0] + "x" + q.get("h", ["0"])[0]
        return f"{task.source}_{h}{variant}{ext}"

    @staticmethod
    def _guess_ext(url: str) -> str:
        path = url.split("?")[0].lower()
        for e in MEDIA_EXTS:
            if path.endswith(e):
                return e
        return ".jpg"

    @staticmethod
    def _fallbacks(url: str) -> list:
        base = url.split("?")[0]
        alts = []
        for e in (".png", ".webp", ".jpg", ".jpeg"):
            a = re.sub(r"\.(png|webp|jpg|jpeg|gif|avif)(\?|$)", e, base)
            if a != base:
                alts.append(a)
        return alts

    @staticmethod
    def _derive_referer(url: str) -> str:
        try:
            from urllib.parse import urlparse
            netloc = urlparse(url).netloc
            return f"https://{netloc}/" if netloc else ""
        except Exception:
            return ""
