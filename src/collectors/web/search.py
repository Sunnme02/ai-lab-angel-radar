"""搜索/新闻线索(基础版):用 DuckDuckGo HTML 端点做轻量网页搜索,无需 key。

仅用于补充"产业/创业"弱信号线索;失败不影响 pipeline。
"""
import urllib.parse

from bs4 import BeautifulSoup

from ...utils.logging import get_logger
from ...utils.rate_limit import get_text

log = get_logger()


def web_search(query: str, max_results=8):
    """返回 [{title, url, snippet}]。尽力而为,失败返回 []。"""
    try:
        html = get_text(f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}",
                        key="ddg", per_sec=1)
    except Exception as e:  # noqa: BLE001
        log.debug(f"web_search 失败 [{query}]: {e}")
        return []
    soup = BeautifulSoup(html, "lxml")
    out = []
    for r in soup.select(".result__body")[:max_results]:
        a = r.select_one("a.result__a")
        sn = r.select_one(".result__snippet")
        if a:
            out.append({"title": a.get_text(" ", strip=True),
                        "url": a.get("href"),
                        "snippet": sn.get_text(" ", strip=True) if sn else ""})
    return out
