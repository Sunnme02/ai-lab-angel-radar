"""Audit a generated graph JSON with optional LLM assistance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .client import LLMClient, LLMConfig
from .graph_context import rule_audit, summarize_graph
from .prompts import GRAPH_AUDIT_SYSTEM, GRAPH_AUDIT_USER


def fallback_markdown(data: dict) -> str:
    summary = summarize_graph(data)
    audit = rule_audit(data)
    lines = [
        "# 图谱审查报告",
        "",
        "本报告由规则审查生成，未调用 LLM。关系结论均应视为公开信号推断。",
        "",
        "## 概览",
        "",
        f"- 节点数：{summary['node_count']}",
        f"- 边数：{summary['edge_count']}",
        f"- 节点类型：{summary['node_type_counts']}",
        f"- 关系类型：{summary['relation_counts']}",
        "",
        "## 高置信推断关系",
        "",
    ]
    if audit["high_confidence"]:
        for item in audit["high_confidence"][:12]:
            lines.append(
                f"- {item['source']} -> {item['target']}："
                f"confidence={item['confidence']:.2f}，共同论文={item['coauthored_papers']}"
            )
    else:
        lines.append("- 暂无。")
    lines.extend(["", "## 需要人工复核", ""])
    if audit["needs_review"]:
        for item in audit["needs_review"][:12]:
            lines.append(
                f"- {item['source']} -> {item['target']}："
                f"confidence={item['confidence']:.2f}，共同论文={item['coauthored_papers']}"
            )
    else:
        lines.append("- 暂无。")
    lines.extend(["", "## 可能误判", ""])
    if audit["possible_false_positive"]:
        for item in audit["possible_false_positive"][:12]:
            lines.append(
                f"- {item['source']} -> {item['target']}：证据较弱，建议查主页或论文作者页。"
            )
    else:
        lines.append("- 暂无明显弱边。")
    lines.extend(
        [
            "",
            "## 下一步建议",
            "",
            "- 对高价值节点人工检查个人主页、实验室成员页和论文作者页。",
            "- 对外展示时使用“学生候选/指导合作推断”，不要写成官方师生关系。",
            "- 对低置信边补充主页证据或在图中降低权重。",
        ]
    )
    return "\n".join(lines) + "\n"


def audit_graph(
    input_path: str | Path,
    *,
    out_path: str | Path | None = None,
    provider: str | None = None,
    model: str | None = None,
    use_llm: bool = True,
) -> Path:
    input_path = Path(input_path)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    client = LLMClient(LLMConfig.from_env(provider=provider, model=model))
    if use_llm and client.available:
        summary = summarize_graph(data)
        markdown = client.complete(
            GRAPH_AUDIT_SYSTEM,
            GRAPH_AUDIT_USER.format(
                summary_json=json.dumps(summary, ensure_ascii=False, indent=2)
            ),
        )
    else:
        markdown = fallback_markdown(data)
    output = Path(out_path) if out_path else input_path.with_name(input_path.stem + "_audit.md")
    output.write_text(markdown.rstrip() + "\n", encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--provider", default=None, choices=["openai", "anthropic"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()

    output = audit_graph(
        args.input,
        out_path=args.out or None,
        provider=args.provider,
        model=args.model,
        use_llm=not args.no_llm,
    )
    print(output)


if __name__ == "__main__":
    main()

