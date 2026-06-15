"""实验室 Angel Radar Score(总分100,规格 7.1 的 7 维规则)。每个分带 reason。"""
from .score_utils import assemble, dim

VERTICAL_DIRECTIONS = {"AI for Finance", "AI for Healthcare", "AI for Education",
                       "Recommendation", "Embodied AI", "Data / Evaluation"}


def score_lab(d: dict):
    """d 字段:
      keyword_paper_count_3y, total_stars, repo_count, high_potential_student_count,
      industry_signal_count, has_joint_lab(bool), has_industry_coauthor(bool),
      directions(set), has_vertical_with_data(bool), pi_has_company(bool),
      pi_has_joint_lab(bool)
    """
    dims = {}

    # 1) 技术前沿性 15
    kp = d.get("keyword_paper_count_3y", 0)
    s = 15 if kp >= 10 else 10 if kp >= 5 else 5 if kp >= 1 else 0
    dims["technical_frontier"] = dim(s, f"近三年方向相关论文 {kp} 篇")

    # 2) 工程化能力 20
    stars = d.get("total_stars", 0)
    rc = d.get("repo_count", 0)
    if rc and stars > 1000:
        s = 20
    elif rc and stars >= 100:
        s = 15
    elif rc:
        s = 8
    elif kp:
        s = 3
    else:
        s = 0
    dims["engineering_signal"] = dim(s, f"GitHub repo {rc} 个,总 stars {stars}")

    # 3) 学生创业潜力 20
    hp = d.get("high_potential_student_count", 0)
    s = 20 if hp >= 5 else 15 if hp >= 3 else 8 if hp >= 1 else 0
    dims["student_potential"] = dim(s, f"高潜学生 {hp} 人")

    # 4) 产业连接 15
    if d.get("has_joint_lab") or (d.get("industry_signal_count", 0) >= 2):
        s = 15
    elif d.get("has_industry_coauthor"):
        s = 10
    elif d.get("industry_signal_count", 0) >= 1:
        s = 5
    else:
        s = 0
    dims["industry_link"] = dim(s, f"产业信号 {d.get('industry_signal_count',0)} 条"
                                   + (",有联合实验室" if d.get("has_joint_lab") else ""))

    # 5) 数据闭环潜力 15
    directions = set(d.get("directions", []))
    vertical = directions & VERTICAL_DIRECTIONS
    if vertical and d.get("has_vertical_with_data"):
        s = 15
    elif vertical:
        s = 10
    elif directions:
        s = 5
    else:
        s = 0
    dims["data_loop"] = dim(s, f"垂直/数据闭环方向: {sorted(vertical) or '通用'}")

    # 6) 商业防御性 10
    if vertical and d.get("has_vertical_with_data"):
        s = 10
    elif "AI Infra" in directions or "LLM Systems" in directions:
        s = 8
    elif "LoRA / PEFT" in directions:
        s = 4
    else:
        s = 2
    dims["defensibility"] = dim(s, "防御性:垂直数据壁垒/工具链/通用微调 视方向而定")

    # 7) 导师转化支持度 5
    if d.get("pi_has_company"):
        s = 5
    elif d.get("pi_has_joint_lab") or d.get("has_joint_lab"):
        s = 3
    else:
        s = 0
    dims["pi_support"] = dim(s, "导师创业/产业转化记录" if d.get("pi_has_company")
                             else "导师联合实验室/企业项目" if d.get("pi_has_joint_lab") else "无明显信号")

    return assemble(dims)
