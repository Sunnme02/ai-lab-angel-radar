"""自动分析文本(规格15节)。有 LLM key 用 LLM,否则模板生成。"""


def template_analysis(lab: dict, top_students, top_directions, signals, score_detail):
    """模板版投资分析(中文)。lab/top_students 为简单 dict/list。"""
    direction = "、".join(top_directions[:3]) or "通用 AI"
    dims = score_detail.get("dimensions", {})
    strong = sorted(dims.items(), key=lambda kv: kv[1]["score"], reverse=True)[:3]
    strong_txt = "、".join(f"{_zh(k)}({v['score']})" for k, v in strong)
    students_txt = "、".join(top_students[:4]) or "暂无明显高潜学生节点"

    angles = []
    if "Recommendation" in top_directions:
        angles.append("推荐/营销场景的垂直大模型应用")
    if "Embodied AI" in top_directions:
        angles.append("具身智能/机器人操作基座")
    if any(d in top_directions for d in ("LLM Systems", "AI Infra", "Inference Optimization")):
        angles.append("LLM 推理/训练系统与 AI Infra 工具链")
    if any(d in top_directions for d in ("LoRA / PEFT", "Model Compression")):
        angles.append("高效微调/模型压缩平台")
    if "AI for Finance" in top_directions:
        angles.append("金融场景 AI(数据闭环强)")
    angles = angles[:3] or ["基于核心论文方向的早期工具/平台型创业"]

    risks = []
    if dims.get("engineering_signal", {}).get("score", 0) <= 3:
        risks.append("工程化/开源信号弱,需补 GitHub 数据或验证落地能力")
    if dims.get("student_potential", {}).get("score", 0) <= 8:
        risks.append("高潜学生节点偏少,创始团队来源待确认")
    if dims.get("pi_support", {}).get("score", 0) == 0:
        risks.append("未见导师创业/转化记录,转化支持度未知")
    risks = risks[:3] or ["方向偏学术热度,需核实商业化路径"]

    return (
        f"该实验室在【{direction}】方向具备一定早期创业潜力。\n"
        f"最强信号:{strong_txt}。\n"
        f"最值得关注的学生/项目节点:{students_txt}。\n"
        f"潜在创业方向:\n" + "".join(f"{i+1}. {a}\n" for i, a in enumerate(angles)) +
        f"主要风险:\n" + "".join(f"{i+1}. {r}\n" for i, r in enumerate(risks)) +
        f"建议接触切入点:优先联系一作高产、且方向偏【{direction}】的高年级博士,"
        f"沿其工程项目与产业合作线索深入。"
    )


def _zh(k):
    return {"technical_frontier": "技术前沿", "engineering_signal": "工程化",
            "student_potential": "学生潜力", "industry_link": "产业连接",
            "data_loop": "数据闭环", "defensibility": "商业防御", "pi_support": "导师支持"}.get(k, k)
