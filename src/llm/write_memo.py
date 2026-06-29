"""Write a short scouting memo from graph JSON, with optional LLM."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .client import LLMClient, LLMConfig
from .graph_context import summarize_graph
from .prompts import MEMO_SYSTEM, MEMO_USER


def fallback_memo(data: dict) -> str:
    summary = summarize_graph(data, max_edges=16, max_nodes=16)
    meta = summary.get("meta", {})
    direction = meta.get("direction") or meta.get("pi_name") or meta.get("name") or "Graph"
    lines = [
        f"# {direction} 图谱简报",
        "",
        "本简报由规则模板生成，未调用 LLM。",
        "",
        "## 范围",
        "",
        f"- 节点数：{summary['node_count']}",
        f"- 边数：{summary['edge_count']}",
        f"- 节点类型：{summary['node_type_counts']}",
        "",
        "## 重点节点",
        "",
    ]
    for node in summary["important_nodes"][:10]:
        lines.append(
            f"- {node.get('label')}（{node.get('type')}，score={node.get('score') or 'n/a'}）"
        )
    lines.extend(["", "## 重点关系", ""])
    for edge in summary["important_edges"][:10]:
        lines.append(
            f"- {edge.get('source')} -> {edge.get('target')}：{edge.get('relation')}，"
            f"strength={edge.get('strength') or edge.get('confidence') or 'n/a'}"
        )
    lines.extend(
        [
            "",
            "## 注意事项",
            "",
            "- 图谱关系来自公开数据和规则推断，适合侦察，不等同于官方事实。",
            "- 对外使用前建议人工复核关键老师、学生候选和共同论文证据。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_memo(
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
            MEMO_SYSTEM,
            MEMO_USER.format(
                summary_json=json.dumps(summary, ensure_ascii=False, indent=2)
            ),
        )
    else:
        markdown = fallback_memo(data)
    output = Path(out_path) if out_path else input_path.with_name(input_path.stem + "_memo.md")
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

    output = write_memo(
        args.input,
        out_path=args.out or None,
        provider=args.provider,
        model=args.model,
        use_llm=not args.no_llm,
    )
    print(output)


if __name__ == "__main__":
    main()

