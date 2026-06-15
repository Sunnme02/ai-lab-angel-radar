"""Repo 产品化评分(总分100,规格 7.3 的 5 维 × 20)。每个分带 reason。"""
import datetime as dt

from .score_utils import assemble, dim


def _days_since(iso):
    if not iso:
        return 9999
    try:
        d = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return (dt.datetime.now(dt.timezone.utc) - d).days
    except Exception:  # noqa: BLE001
        return 9999


def score_repo(r: dict):
    """r 字段:stars,forks,open_issues,last_commit_at,readme_text,topics,
       matched_keywords(list),productization_signal_count,has_vertical_scene(bool)"""
    dims = {}

    # 1) 工程活跃度 20(最近提交 + issues)
    days = _days_since(r.get("last_commit_at"))
    if days <= 90:
        s = 20
    elif days <= 365:
        s = 12
    elif days <= 730:
        s = 6
    else:
        s = 2
    dims["activity"] = dim(s, f"最近提交距今约 {days} 天")

    # 2) 社区关注度 20(stars/forks)
    stars = r.get("stars", 0)
    s = 20 if stars > 1000 else 15 if stars >= 300 else 10 if stars >= 50 else 4 if stars else 0
    dims["community"] = dim(s, f"stars {stars}, forks {r.get('forks',0)}")

    # 3) 产品化程度 20(README 信号 + topics)
    ps = r.get("productization_signal_count", 0)
    s = min(20, ps * 4)
    dims["productization"] = dim(s, f"产品化信号 {ps} 个(install/demo/API/Docker/HF 等)")

    # 4) 技术前沿性 20(命中前沿关键词)
    mk = len(r.get("matched_keywords", []) or [])
    s = min(20, mk * 5)
    dims["frontier"] = dim(s, f"命中前沿关键词 {mk} 个: {list(r.get('matched_keywords',[]))[:4]}")

    # 5) 商业场景明确度 20
    s = 20 if r.get("has_vertical_scene") else 8 if mk else 0
    dims["business_scene"] = dim(s, "有明确垂直应用场景" if r.get("has_vertical_scene")
                                 else "通用方法,潜在场景" if mk else "场景不明确")

    return assemble(dims)
