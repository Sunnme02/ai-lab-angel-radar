"""机构/公司名规范化(规格 8.6)。"""
import re


def normalize_org(name: str) -> str:
    if not name:
        return ""
    s = name.strip()
    s = re.sub(r"\b(inc\.?|ltd\.?|co\.,?|corp\.?|company|有限公司|股份)\b", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" ,.")
    return s


def same_org(a: str, b: str) -> bool:
    from rapidfuzz import fuzz
    return fuzz.token_set_ratio(normalize_org(a).lower(), normalize_org(b).lower()) >= 90
