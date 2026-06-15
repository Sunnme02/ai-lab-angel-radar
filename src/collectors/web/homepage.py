"""网页采集:抓主页/实验室页 → 正文、链接、成员/产业信号关键词(规格 8.4)。

requests + BeautifulSoup;动态网页预留 Playwright(默认不启用)。
"""
from bs4 import BeautifulSoup

from ...utils.logging import get_logger
from ...utils.rate_limit import get_text

log = get_logger()

MEMBER_KW = ["students", "phd", "master", "alumni", "publications", "projects",
             "github", "startup", "company", "collaboration", "joint lab",
             "成员", "学生", "博士", "硕士", "校友", "论文", "项目", "合作", "创业", "成果转化"]


def fetch_homepage(url: str):
    """返回 {title, text, links, github_links, member_signal_keywords} 或 None。"""
    if not url:
        return None
    try:
        html = get_text(url, key="web", per_sec=3)
    except Exception as e:  # noqa: BLE001
        log.debug(f"抓主页失败 {url}: {e}")
        return None
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.string if soup.title else "") or ""
    text = soup.get_text(" ", strip=True)[:20000]
    links = []
    github_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        links.append(href)
        if "github.com" in href:
            github_links.append(href)
    low = text.lower()
    found = [kw for kw in MEMBER_KW if kw in low]
    return {
        "title": title.strip(),
        "text": text,
        "links": list(dict.fromkeys(links))[:200],
        "github_links": list(dict.fromkeys(github_links))[:50],
        "member_signal_keywords": found,
    }
