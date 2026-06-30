"""给 Spyder / VS Code / 其他 IDE 使用的一键运行入口。

用法：
1. 只改下面几个配置区。
2. 直接运行这个文件。
3. 生成结果会打印在控制台，HTML/JSON 会写入 data/exports/。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.graph.export_direction_graph import export_direction_graph
from src.graph.export_pi_ego_graph import export_pi_ego_graph
from src.llm.audit_graph import audit_graph
from src.llm.expand_direction import expand_direction
from src.llm.write_memo import write_memo


ROOT = Path(__file__).resolve().parent


# ============================================================
# 1. 选择你这次要运行什么
# ============================================================

# 可选值：
# "direction"  = 按 AI 方向生成图谱
# "professor"  = 按老师名字生成恒星图
# "update_all" = 更新全部 seed 实验室数据，耗时较久
# "update_lab" = 只更新一个老师/实验室的数据
RUN_TASK = "professor"


# ============================================================
# 2. 方向图参数：RUN_TASK = "direction" 时使用
# ============================================================

DIRECTION_CONFIG = {
    # 你想看的方向名。例子："Agent"、"具身智能"、"AI Infra"、"多模态"
    "direction": "AI Infra",

    # 方向关键词。可留空；留空时只用 direction 本身搜索。
    # 建议填几个同义词/英文词，命中会更准。
    "keywords": "",

    # True = 自动扩展关键词。
    # use_llm=False 时走内置模板；use_llm=True 时会尝试调用 LLM。
    "auto_keywords": True,

    # 最多展示多少个相关实验室/老师。
    "max_labs": 12,

    # 每个老师最多展开多少个学生候选。
    "max_students_per_lab": 6,
}


# ============================================================
# 3. 老师恒星图参数：RUN_TASK = "professor" 时使用
# ============================================================

PROFESSOR_CONFIG = {
    # 老师英文名。必须是当前数据库里已有的 PI 名字。
    "pi_name": "Fuchun Sun",

    # 老师图里最多展示多少个学生候选。
    "max_students": 16,
}


# ============================================================
# 4. 数据更新参数：RUN_TASK = "update_all" 或 "update_lab" 时使用
# ============================================================

DATA_UPDATE_CONFIG = {
    # update_all：是否跳过 GitHub 采集。
    # True 更快，也不需要 GITHUB_TOKEN；但 repo/project 工程信号会偏少。
    "no_github": True,

    # update_all：只更新前 N 个实验室。None = 全部更新。
    # 调试时可以先设成 2，确认流程跑通。
    "limit_labs": None,

    # update_all：自定义 seed 文件。None = 使用默认 seed。
    "seed_files": None,

    # update_lab：只更新单个老师/实验室时填写。
    "pi_name": "Fuchun Sun",
    "school": "Tsinghua University",
    "pi_name_cn": "",
    "homepage": "",
    "keywords": "Embodied AI,robot learning,robot manipulation",
}


# ============================================================
# 5. 审查 / 简报参数：生成方向图或老师图后可选运行
# ============================================================

REVIEW_CONFIG = {
    # True = 生成关系审查报告。
    "run_audit": False,

    # True = 生成一份图谱简报。
    "write_memo": False,
}


# ============================================================
# 6. LLM 参数：默认关闭，避免没配置 key 时报错
# ============================================================

LLM_CONFIG = {
    # False = 不调用 LLM，只用规则模板。
    "use_llm": False,

    # 如果 use_llm=True，可填 "openai" 或 "anthropic"。
    # 不用 LLM 时保持 None。
    "provider": None,

    # 可指定模型；不填则用项目默认模型。
    "model": None,


}


def _print_result(title: str, result: dict) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("html"):
        print(f"\nHTML: {Path(result['html']).resolve()}")
    if result.get("json"):
        print(f"JSON: {Path(result['json']).resolve()}")


def _expand_direction_keywords() -> str:
    if not DIRECTION_CONFIG["auto_keywords"]:
        return DIRECTION_CONFIG["keywords"]

    data = expand_direction(
        DIRECTION_CONFIG["direction"],
        provider=LLM_CONFIG["provider"],
        model=LLM_CONFIG["model"],
        use_llm=LLM_CONFIG["use_llm"],
    )
    keywords = [
        keyword
        for keyword in data.get("keywords", [])
        if keyword != DIRECTION_CONFIG["direction"]
    ]
    return ",".join(keywords)


def run_direction_graph() -> dict:
    keywords = _expand_direction_keywords()
    return export_direction_graph(
        DIRECTION_CONFIG["direction"],
        keywords,
        max_labs=DIRECTION_CONFIG["max_labs"],
        max_students_per_lab=DIRECTION_CONFIG["max_students_per_lab"],
    )


def run_professor_graph() -> dict:
    return export_pi_ego_graph(
        PROFESSOR_CONFIG["pi_name"],
        max_students=PROFESSOR_CONFIG["max_students"],
    )


def run_reviews(graph_json: str) -> None:
    if REVIEW_CONFIG["run_audit"]:
        audit_path = audit_graph(
            graph_json,
            provider=LLM_CONFIG["provider"],
            model=LLM_CONFIG["model"],
            use_llm=LLM_CONFIG["use_llm"],
        )
        print(f"Audit: {audit_path.resolve()}")

    if REVIEW_CONFIG["write_memo"]:
        memo_path = write_memo(
            graph_json,
            provider=LLM_CONFIG["provider"],
            model=LLM_CONFIG["model"],
            use_llm=LLM_CONFIG["use_llm"],
        )
        print(f"Memo: {memo_path.resolve()}")


def update_all_data() -> None:
    args = [sys.executable, "-m", "src.pipeline.run_all"]

    if DATA_UPDATE_CONFIG["no_github"]:
        args.append("--no-github")

    if DATA_UPDATE_CONFIG["limit_labs"] is not None:
        args.extend(["--limit-labs", str(DATA_UPDATE_CONFIG["limit_labs"])])

    if DATA_UPDATE_CONFIG["seed_files"]:
        args.append("--seeds")
        args.extend(DATA_UPDATE_CONFIG["seed_files"])

    print("\n=== 开始更新全部 seed 数据 ===")
    print(" ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)
    print("=== 数据更新完成 ===")


def update_one_lab() -> None:
    args = [
        sys.executable,
        "-m",
        "src.pipeline.run_lab",
        "--pi",
        DATA_UPDATE_CONFIG["pi_name"],
        "--school",
        DATA_UPDATE_CONFIG["school"],
    ]

    if DATA_UPDATE_CONFIG["pi_name_cn"]:
        args.extend(["--pi-cn", DATA_UPDATE_CONFIG["pi_name_cn"]])
    if DATA_UPDATE_CONFIG["homepage"]:
        args.extend(["--homepage", DATA_UPDATE_CONFIG["homepage"]])
    if DATA_UPDATE_CONFIG["keywords"]:
        args.extend(["--keywords", DATA_UPDATE_CONFIG["keywords"]])

    print("\n=== 开始更新单个老师/实验室数据 ===")
    print(" ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)
    print("=== 单个老师/实验室更新完成 ===")


def main() -> None:
    task = RUN_TASK.strip().lower()

    if task == "direction":
        result = run_direction_graph()
        _print_result("方向图已生成", result)
        if result.get("json"):
            run_reviews(result["json"])
        return

    if task == "professor":
        result = run_professor_graph()
        _print_result("老师恒星图已生成", result)
        if result.get("json"):
            run_reviews(result["json"])
        return

    if task == "update_all":
        update_all_data()
        return

    if task == "update_lab":
        update_one_lab()
        return

    raise ValueError(
        'RUN_TASK 只能是 "direction"、"professor"、"update_all" 或 "update_lab"。'
    )


if __name__ == "__main__":
    main()
