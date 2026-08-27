# -*- coding: utf-8 -*-
"""
crawler_kit —— 爬虫共享运行时库（PLUGIN_SPEC 纪律 5）

三件全提（2026-08-27，用户拍板）：
  - downloader.py  通用异步下载器（限速/重试/断点续传/防盗链）← image-scraper sources/base.py
  - identity.py    浏览器身份池（UA/指纹轮换 + 请求头构建）       ← webcopier identity_manager.py
  - session.py     登录态与 Cookie（Netscape 解析/持久化 + Playwright 导出）← bilibili-helper-py cookie_utils.py + webcopier session.py

引用不融合：插件 import 本库并声明依赖版本（manifest 的 kit 字段）；库有版本、插件声明版本。
"""

__version__ = "1.0.0"

from .downloader import Task, Downloader  # noqa: F401
from .identity import BrowserIdentityManager, get_identity_manager  # noqa: F401
from .session import (  # noqa: F401
    parse_netscape_cookies,
    cookies_to_netscape,
    cookie_str,
    save_cookies_to_file,
    load_cookies_from_file,
    export_cookies_with_playwright,
)
