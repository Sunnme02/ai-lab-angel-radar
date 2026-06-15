"""学生创业潜力评分(总分100,规格 7.2 的 7 维)。每个分带 reason。"""
from .score_utils import assemble, dim


def score_person(d: dict):
    """d 字段:
      first_author_count_3y, related_paper_count, max_repo_stars, repo_count,
      repo_active(bool), matched_keyword_count, productization_signal_count,
      industry_signal_count, centrality(0-1), role
    """
    dims = {}

    # 1) 论文能力 20
    fa = d.get("first_author_count_3y", 0)
    if fa >= 3:
        s = 20
    elif fa >= 1:
        s = 15
    elif d.get("related_paper_count", 0) >= 3:
        s = 8
    else:
        s = min(5, d.get("related_paper_count", 0) * 2)
    dims["paper_ability"] = dim(s, f"近三年一作 {fa} 篇,相关论文 {d.get('related_paper_count',0)} 篇")

    # 2) 工程能力 25
    stars = d.get("max_repo_stars", 0)
    rc = d.get("repo_count", 0)
    if stars > 1000:
        s = 25
    elif stars >= 100:
        s = 18
    elif rc and d.get("repo_active"):
        s = 12
    elif rc:
        s = 5
    else:
        s = 0
    dims["engineering"] = dim(s, f"repo {rc} 个,最高 stars {stars}")

    # 3) 前沿方向匹配 15
    mk = d.get("matched_keyword_count", 0)
    s = min(15, mk * 4)
    dims["frontier_match"] = dim(s, f"命中前沿关键词 {mk} 个")

    # 4) 产品化倾向 15
    ps = d.get("productization_signal_count", 0)
    s = min(15, ps * 4)
    dims["productization"] = dim(s, f"产品化信号 {ps} 个(demo/API/Docker/HF/benchmark 等)")

    # 5) 产业连接 10
    isig = d.get("industry_signal_count", 0)
    s = min(10, isig * 5)
    dims["industry_link"] = dim(s, f"产业连接信号 {isig} 个")

    # 6) 网络中心性 10
    cen = d.get("centrality", 0) or 0
    s = round(min(10, cen * 10), 1)
    dims["centrality"] = dim(s, f"图谱中心性(归一) {cen:.3f}")

    # 7) 创业窗口 5
    role = (d.get("role") or "Unknown")
    s = {"PhD": 5, "Researcher": 5, "Master": 3, "Undergraduate": 2}.get(role, 1)
    dims["startup_window"] = dim(s, f"角色={role}(高年级博士/博后给高分,Unknown 不强给)")

    return assemble(dims)
