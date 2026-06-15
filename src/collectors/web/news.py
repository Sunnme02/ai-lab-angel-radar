"""新闻/产业线索:基于 web_search 找实验室/PI 的产业合作、创业、融资线索(弱信号)。"""
from .search import web_search

COMPANY_HINTS = ["创业", "融资", "成立", "公司", "联合实验室", "成果转化", "孵化",
                 "startup", "funding", "spin-off", "co-founder", "company"]


def find_industry_signals(pi_name_cn_or_en: str, school: str = "", max_results=6):
    """搜 'PI + 创业/公司' 类线索,返回命中 company-hint 的结果。"""
    q = f"{pi_name_cn_or_en} {school} 创业 公司 融资".strip()
    results = web_search(q, max_results=max_results)
    out = []
    for r in results:
        blob = (r.get("title", "") + " " + r.get("snippet", "")).lower()
        hits = [h for h in COMPANY_HINTS if h.lower() in blob]
        if hits:
            out.append({**r, "signal_hits": hits})
    return out
