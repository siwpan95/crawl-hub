# crawler_kit —— 爬虫共享运行时库（PLUGIN_SPEC 纪律 5）

> 三件全提（2026-08-27，用户拍板）：**Downloader**（限速/重试/断点续传/防盗链）+ **身份池**（UA/指纹轮换）+ **登录态**（Netscape Cookie / Playwright 导出）。

## 来源记账（借鉴必记账）

| 模块 | 提炼自 | 说明 |
|---|---|---|
| `downloader.py` | image-scraper `sources/base.py`（Downloader/ImageTask） | 通用化为 `Task`，能力同源 |
| `identity.py` | webcopier `identity_manager.py` | 内置 5 身份回退池；外部 identities.json 可选 |
| `session.py` | bilibili-helper-py `cookie_utils.py` + webcopier `session.py` | Netscape 解析/序列化 + JSON 持久化 + Playwright 导出 |

## 用法

```python
from crawler_kit import Downloader, Task, get_identity_manager

# 身份池（UA/指纹轮换 + 请求头构建）
mgr = get_identity_manager()
identity = mgr.get_identity(0)               # 索引轮换（取模）
headers = mgr.build_headers(identity, referer="https://x.com/")

# 下载器
dl = Downloader(output_dir, concurrency=5, retries=3, rate_limit=2, speed_limit=500)
tasks = [Task(url="https://x.com/a.jpg", source="demo", referer="https://x.com/")]
# asyncio.run(dl.download_batch(tasks)); await dl.close()

# 登录态
from crawler_kit.session import parse_netscape_cookies, export_cookies_with_playwright
cookies = parse_netscape_cookies("cookies.txt")
```

## 纪律

- **引用不融合**：插件在 manifest 声明依赖版本 `kit: {downloader: ^1, identity: ^1, session: ^1}`；库有版本、插件声明版本。
- **敏感信息红线**：Cookie/登录态/代理凭据一律本地文件（.gitignore），不进仓、不进 manifest。
- 依赖：httpx（downloader）、requests（session 持久化）、playwright（仅导出函数，运行时导入）。
- 测试：`crawler_kit/test_kit.py`（unittest，无网络）——改库后必须全绿，harness `plugin-audit` 黄金值同时校验库可导入。
