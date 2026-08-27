# -*- coding: utf-8 -*-
"""crawler_kit 自测（无网络；harness plugin-audit 黄金值依赖其全绿）"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler_kit import (  # noqa: E402
    Task, Downloader, BrowserIdentityManager, get_identity_manager,
    parse_netscape_cookies, cookies_to_netscape, cookie_str,
    save_cookies_to_file, load_cookies_from_file,
)


class DownloaderTests(unittest.TestCase):
    def test_guess_ext(self):
        self.assertEqual(Downloader._guess_ext("https://x.com/a.png?w=1"), ".png")
        self.assertEqual(Downloader._guess_ext("https://x.com/b"), ".jpg")

    def test_fallbacks(self):
        fb = Downloader._fallbacks("https://x.com/a.jpg")
        self.assertIn("https://x.com/a.png", fb)
        self.assertIn("https://x.com/a.webp", fb)

    def test_derive_referer(self):
        self.assertEqual(Downloader._derive_referer("https://cdn.x.com/i.jpg"), "https://cdn.x.com/")
        self.assertEqual(Downloader._derive_referer("bad url"), "")

    def test_make_filename_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            dl = Downloader(Path(tmp))
            t = Task(url="https://x.com/a.jpg", source="demo")
            f1 = dl._make_filename(t)
            f2 = dl._make_filename(t)
            self.assertEqual(f1, f2)
            self.assertTrue(f1.startswith("demo_"))
            self.assertTrue(f1.endswith(".jpg"))


class IdentityTests(unittest.TestCase):
    def test_fallback_pool(self):
        mgr = BrowserIdentityManager(identities_path=None)
        self.assertGreaterEqual(mgr.count, 5)

    def test_rotation(self):
        mgr = BrowserIdentityManager(identities_path=None)
        n = mgr.count
        self.assertEqual(mgr.get_identity(0)["id"], mgr.get_identity(n)["id"])

    def test_build_headers(self):
        mgr = BrowserIdentityManager(identities_path=None)
        h = mgr.build_headers(mgr.get_identity(0), referer="https://r.com/", cookie_str="a=1")
        self.assertIn("User-Agent", h)
        self.assertEqual(h["Referer"], "https://r.com/")
        self.assertEqual(h["Cookie"], "a=1")
        self.assertIn("_curl_impersonate", h)

    def test_singleton(self):
        self.assertIs(get_identity_manager(), get_identity_manager())


class SessionTests(unittest.TestCase):
    def test_netscape_roundtrip(self):
        cookies = [{"name": "SESSDATA", "value": "abc", "domain": ".bilibili.com",
                    "path": "/", "expires": "0", "secure": False, "http_only": True}]
        text = cookies_to_netscape(cookies)
        parsed = parse_netscape_cookies(_write_tmp(text))
        self.assertEqual(parsed[0]["name"], "SESSDATA")
        self.assertEqual(parsed[0]["value"], "abc")
        self.assertTrue(parsed[0]["http_only"])

    def test_cookie_str(self):
        self.assertEqual(cookie_str([{"name": "a", "value": "1"}, {"name": "b", "value": "2"}]), "a=1; b=2")

    def test_json_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "c.json")
            self.assertTrue(save_cookies_to_file({"k": "v"}, p))
            self.assertEqual(load_cookies_from_file(p), {"k": "v"})
            self.assertEqual(load_cookies_from_file(os.path.join(tmp, "nope.json")), {})


def _write_tmp(text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path


if __name__ == "__main__":
    unittest.main(verbosity=2)
