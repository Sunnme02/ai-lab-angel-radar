"""评分通用工具:组装 dimension、优先级。"""


def dim(score, reason):
    return {"score": score, "reason": reason}


def assemble(dimensions: dict):
    """dimensions={name:{score,reason}} → {total_score, dimensions}。"""
    total = sum(d["score"] for d in dimensions.values())
    return {"total_score": round(total, 1), "dimensions": dimensions}


def priority(score):
    if score >= 80:
        return "High"
    if score >= 65:
        return "Medium High"
    if score >= 50:
        return "Medium"
    return "Low"


def contact_priority(score):
    if score >= 75:
        return "High"
    if score >= 55:
        return "Medium High"
    if score >= 40:
        return "Medium"
    return "Low"
