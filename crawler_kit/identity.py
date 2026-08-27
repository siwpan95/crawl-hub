# -*- coding: utf-8 -*-
"""
浏览器身份池（crawler_kit.identity）

来源记账（借鉴必记账）：提炼自 G:\\repos\\webcopier\\webcopier\\identity_manager.py
（2026-08-27 crawler-kit P3）。能力：
  - 从 identities.json 加载身份池（UA + 浏览器指纹 + curl_cffi 指纹别名）
  - 索引轮换 / 随机取用（身份数 = 建议最大重试次数）
  - 构建完整请求头（含 sec-ch-ua 指纹、Referer、Cookie 注入）
内置最小回退池（5 个桌面/移动端身份），外部 JSON 缺失时自动降级。
"""

import json
import os
import random

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}

_FALLBACK_IDENTITIES = [
    {
        "id": "chrome-win-130",
        "engine": "chrome", "platform": "desktop",
        "os": "Windows NT 10.0; Win64; x64",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "curl_impersonate": "chrome120",
        "headers": {
            "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
    },
    {
        "id": "firefox-win-133",
        "engine": "firefox", "platform": "desktop",
        "os": "Windows NT 10.0; Win64; x64; rv:133.0",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) "
              "Gecko/20100101 Firefox/133.0",
        "curl_impersonate": "firefox116",
        "headers": {},
    },
    {
        "id": "safari-mac-18_3",
        "engine": "safari", "platform": "desktop",
        "os": "Macintosh; Intel Mac OS X 10_15_7",
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Version/18.3 Safari/605.1.15",
        "curl_impersonate": "safari17_0",
        "headers": {},
    },
    {
        "id": "edge-win-130",
        "engine": "edge", "platform": "desktop",
        "os": "Windows NT 10.0; Win64; x64",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
        "curl_impersonate": "edge101",
        "headers": {
            "sec-ch-ua": '"Chromium";v="130", "Microsoft Edge";v="130", "Not?A_Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
    },
    {
        "id": "chrome-android-130",
        "engine": "chrome", "platform": "mobile",
        "os": "Linux; Android 14; Pixel 8 Pro",
        "ua": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
        "curl_impersonate": "chrome120",
        "headers": {
            "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
        },
    },
]


class BrowserIdentityManager:
    """浏览器身份池管理器（外部 identities.json 缺失时用内置回退池）。"""

    def __init__(self, identities_path=None):
        self._path = identities_path
        self._identities = []
        self._load()

    def _load(self):
        if self._path:
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                loaded = data.get("identities", [])
                if loaded:
                    self._identities = loaded
                    return
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                pass
        self._identities = list(_FALLBACK_IDENTITIES)

    @property
    def count(self) -> int:
        return len(self._identities)

    @property
    def identities(self):
        return list(self._identities)

    def get_identity(self, index: int) -> dict:
        if not self._identities:
            raise RuntimeError("身份池为空，无法获取身份")
        return self._identities[index % len(self._identities)]

    def get_random_identity(self) -> dict:
        if not self._identities:
            raise RuntimeError("身份池为空")
        return random.choice(self._identities)

    def get_ua(self, identity: dict) -> str:
        return identity.get("ua", "")

    def get_random_ua(self) -> str:
        return self.get_ua(self.get_random_identity())

    def get_curl_impersonate(self, identity: dict) -> str:
        return identity.get("curl_impersonate", "chrome120")

    def build_headers(self, identity: dict, referer=None, cookie_str=None) -> dict:
        """基于 identity 构建完整请求头（含浏览器指纹、Referer、Cookie；
        _curl_impersonate 为内部透传键，请求前 pop 掉）。"""
        headers = dict(DEFAULT_HEADERS)
        headers["User-Agent"] = identity.get("ua", DEFAULT_HEADERS["User-Agent"])
        id_headers = identity.get("headers", {})
        if id_headers:
            for key in ("sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform"):
                if key in id_headers:
                    headers[key] = id_headers[key]
                else:
                    headers.pop(key, None)
        if referer:
            headers["Referer"] = referer
        if cookie_str:
            headers["Cookie"] = cookie_str
        headers["_curl_impersonate"] = identity.get("curl_impersonate", "")
        return headers


_default_manager = None


def get_identity_manager() -> BrowserIdentityManager:
    """模块级单例（避免重复加载 JSON）。"""
    global _default_manager
    if _default_manager is None:
        _default_manager = BrowserIdentityManager()
    return _default_manager
