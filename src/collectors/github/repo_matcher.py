"""Repo ↔ 人 匹配,保留 confidence(规格 8.5 的匹配策略)。"""
from rapidfuzz import fuzz

from ...utils.text import normalize_name


def match_repo_to_person(repo: dict, person_name: str, person_homepage: str = "",
                         paper_titles=None):
    """返回 (link_type, confidence) 或 (None, 0)。

    - 主页直链 GitHub → 1.0
    - GitHub 用户名出现在主页 → 0.9
    - README 提到论文标题 → 0.85
    - owner 名与人名 fuzzy match 且 topic/关键词匹配 → 0.6
    - 低于 0.6 仅作 candidate
    """
    owner = (repo.get("owner") or "")
    homepage = (person_homepage or "")
    if owner and homepage and owner.lower() in homepage.lower():
        return "homepage_link", 1.0
    if owner and homepage and f"github.com/{owner.lower()}" in homepage.lower():
        return "homepage_link", 0.9

    readme = (repo.get("readme_text") or "")
    if paper_titles:
        for t in paper_titles:
            if t and len(t) > 15 and t.lower() in readme.lower():
                return "mentioned_in_readme", 0.85

    # owner 名与人名 fuzzy
    nm = normalize_name(person_name)
    own = normalize_name(owner)
    score = fuzz.token_set_ratio(nm, own) / 100.0 if own else 0
    if score >= 0.8:
        return "owner", round(0.6 + (score - 0.8), 2)
    if score >= 0.55:
        return "fuzzy_match", round(score, 2)
    return None, 0.0
