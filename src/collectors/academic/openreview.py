"""OpenReview 采集器:抓 ICLR/NeurIPS/ICML 等会议论文(基础版/预留接口)。

第一版只做按 venueid 的基础搜索;主力学术信号走 OpenAlex。
"""
import urllib.parse

from ...utils.logging import get_logger
from ...utils.rate_limit import get_json

log = get_logger()
API2 = "https://api2.openreview.net"


class OpenReviewCollector:
    def accepted_notes(self, venueid: str, limit=50):
        """取某 venue 的已录用论文(基础)。返回精简列表。"""
        try:
            d = get_json(f"{API2}/notes", key="openreview", per_sec=3,
                         params={"content.venueid": venueid, "limit": limit})
        except Exception as e:  # noqa: BLE001
            log.debug(f"OpenReview 失败 {venueid}: {e}")
            return []
        out = []
        for n in d.get("notes", []):
            c = n.get("content", {})
            def gv(k):
                v = c.get(k, {})
                return v.get("value") if isinstance(v, dict) else v
            out.append({
                "title": gv("title"),
                "authors": gv("authors") or [],
                "abstract": gv("abstract"),
                "keywords": gv("keywords") or [],
                "url": f"https://openreview.net/forum?id={n.get('forum')}",
                "source": "openreview",
            })
        return out
