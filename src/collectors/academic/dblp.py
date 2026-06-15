"""DBLP 采集器:补充 CS 论文/会议(基础版)。无机构信息。"""
from ...utils.logging import get_logger
from ...utils.rate_limit import get_json

log = get_logger()
BASE = "https://dblp.org/search/publ/api"


class DBLPCollector:
    def search_pi(self, pi_name: str, max_hits=30):
        """按 PI 名搜其论文(DBLP),返回精简列表(标题/年/venue/url)。"""
        try:
            d = get_json(BASE, key="dblp", per_sec=2,
                         params={"q": pi_name, "h": max_hits, "format": "json"})
        except Exception as e:  # noqa: BLE001
            log.debug(f"DBLP 失败 {pi_name}: {e}")
            return []
        hits = (((d or {}).get("result") or {}).get("hits") or {}).get("hit", [])
        out = []
        for h in hits:
            info = h.get("info", {})
            out.append({
                "title": info.get("title"),
                "year": int(info.get("year")) if info.get("year") else None,
                "venue": info.get("venue"),
                "url": info.get("ee") or info.get("url"),
                "source": "dblp",
            })
        return out
