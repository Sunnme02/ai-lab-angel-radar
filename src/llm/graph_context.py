"""Compact graph JSON into LLM-friendly summaries."""
from __future__ import annotations

from collections import Counter


def summarize_graph(data: dict, max_edges: int = 24, max_nodes: int = 36) -> dict:
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    node_by_id = {node.get("id"): node for node in nodes}
    type_counts = Counter(node.get("type", "unknown") for node in nodes)
    relation_counts = Counter(edge.get("relation", "unknown") for edge in edges)

    important_nodes = sorted(
        nodes,
        key=lambda node: float(node.get("score") or node.get("size") or 0),
        reverse=True,
    )[:max_nodes]

    def edge_strength(edge: dict) -> float:
        return float(
            edge.get("strength")
            or edge.get("weight")
            or edge.get("confidence")
            or edge.get("coauthored_papers")
            or 0
        )

    important_edges = sorted(edges, key=edge_strength, reverse=True)[:max_edges]
    readable_edges = []
    for edge in important_edges:
        source = node_by_id.get(edge.get("source"), {})
        target = node_by_id.get(edge.get("target"), {})
        readable_edges.append(
            {
                "source": source.get("label", edge.get("source")),
                "target": target.get("label", edge.get("target")),
                "relation": edge.get("relation"),
                "confidence": edge.get("confidence"),
                "coauthored_papers": edge.get("coauthored_papers"),
                "strength": edge.get("strength") or edge.get("weight"),
                "evidence": (edge.get("evidence") or [])[:4],
                "title": edge.get("title"),
            }
        )

    return {
        "meta": data.get("meta", {}),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_type_counts": dict(type_counts),
        "relation_counts": dict(relation_counts),
        "important_nodes": [
            {
                "label": node.get("label"),
                "type": node.get("type"),
                "score": node.get("score"),
                "school": node.get("school") or node.get("affiliation"),
                "title": node.get("title"),
            }
            for node in important_nodes
        ],
        "important_edges": readable_edges,
    }


def rule_audit(data: dict) -> dict:
    """Deterministic fallback audit for relationship graphs."""
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    node_by_id = {node.get("id"): node for node in nodes}
    high_confidence = []
    needs_review = []
    possible_false_positive = []

    for edge in edges:
        relation = edge.get("relation")
        if relation not in {"ADVISES", "ADVISES_AND_COLLABORATES"}:
            continue
        source = node_by_id.get(edge.get("source"), {})
        target = node_by_id.get(edge.get("target"), {})
        confidence = float(edge.get("confidence") or 0)
        coauthored = int(edge.get("coauthored_papers") or 0)
        item = {
            "source": source.get("label", edge.get("source")),
            "target": target.get("label", edge.get("target")),
            "confidence": confidence,
            "coauthored_papers": coauthored,
            "evidence": (edge.get("evidence") or [])[:4],
        }
        if confidence >= 0.75 and coauthored >= 2:
            high_confidence.append(item)
        elif confidence < 0.55 or coauthored == 0:
            possible_false_positive.append(item)
        else:
            needs_review.append(item)

    return {
        "high_confidence": high_confidence[:20],
        "needs_review": needs_review[:20],
        "possible_false_positive": possible_false_positive[:20],
    }

