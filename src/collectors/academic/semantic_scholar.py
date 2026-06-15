"""Semantic Scholar 采集器:补充作者 h-index / 引用 / S2 author id。

无 key 也能用(限流更严,带退避)。
"""
from ...utils.logging import get_logger
from ...utils.rate_limit import get_json

log = get_logger()
BASE = "https://api.semanticscholar.org/graph/v1"


class SemanticScholarCollector:
    def __init__(self, api_key: str = ""):
        self.headers = {"x-api-key": api_key} if api_key else None

    def search_author(self, name: str):
        """按姓名搜作者,返回首个 {authorId,name,hIndex,citationCount,paperCount,affiliations} 或 None。"""
        try:
            d = get_json(f"{BASE}/author/search", key="s2", per_sec=1, headers=self.headers,
                         params={"query": name,
                                 "fields": "name,hIndex,citationCount,paperCount,affiliations"})
        except Exception as e:  # noqa: BLE001
            log.debug(f"S2 搜作者失败 {name}: {e}")
            return None
        data = d.get("data", [])
        if not data:
            return None
        # 取论文数最多的候选,减少碎片化档案
        return max(data, key=lambda a: a.get("paperCount") or 0)

    def author_metrics(self, name: str):
        a = self.search_author(name)
        if not a:
            return None
        return {
            "semantic_scholar_author_id": a.get("authorId"),
            "h_index": a.get("hIndex"),
            "citations": a.get("citationCount"),
            "paper_count": a.get("paperCount"),
        }
