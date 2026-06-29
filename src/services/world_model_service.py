"""Reusable World Model graph service.

The service works from the generated graph JSON so web APIs, local scripts and
future agent skills all use the same filtering semantics as the HTML export.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..graph.export_world_model_graph import EXPORTS_DIR, TRACKS, export_world_model_graph

GRAPH_JSON = EXPORTS_DIR / "world_model_graph.json"

DIRECTION_ALIASES = {
    "core": "core",
    "world-model": "core",
    "world_model": "core",
    "world model": "core",
    "embodied": "embodied",
    "robot": "embodied",
    "robotics": "embodied",
    "具身": "embodied",
    "机器人": "embodied",
    "driving": "driving",
    "autonomous-driving": "driving",
    "autonomous_driving": "driving",
    "4d": "driving",
    "自动驾驶": "driving",
}


def normalize_direction(direction: str) -> str:
    key = (direction or "").strip().lower()
    key = DIRECTION_ALIASES.get(key, key)
    if key not in TRACKS:
        allowed = ", ".join(TRACKS)
        raise ValueError(f"unknown direction '{direction}'. Expected one of: {allowed}")
    return key


def load_graph(path: str | Path = GRAPH_JSON) -> dict:
    path = Path(path)
    if not path.exists():
        export_world_model_graph(out_dir=path.parent)
    return json.loads(path.read_text(encoding="utf-8"))


def directions() -> list[dict]:
    return [
        {"key": key, "label": spec["label"], "patterns": spec["patterns"]}
        for key, spec in TRACKS.items()
    ]


def _index(data: dict):
    nodes = {node["id"]: node for node in data.get("nodes", [])}
    edges = data.get("edges", [])
    labels = {node["id"]: node.get("label", node["id"]) for node in data.get("nodes", [])}
    return nodes, edges, labels


def _subgraph(data: dict, ids: set[str]) -> dict:
    nodes = [node for node in data.get("nodes", []) if node["id"] in ids]
    keep = {node["id"] for node in nodes}
    edges = [
        edge for edge in data.get("edges", [])
        if edge.get("source") in keep and edge.get("target") in keep
    ]
    return {"meta": data.get("meta", {}), "nodes": nodes, "edges": edges}


def direction_subgraph(direction: str, path: str | Path = GRAPH_JSON) -> dict:
    data = load_graph(path)
    direction_key = normalize_direction(direction)
    track_id = f"track:{direction_key}"
    ids = {"direction:world_model", track_id}
    matched_people = set()

    for edge in data.get("edges", []):
        if edge.get("relation") != "MATCHES_DIRECTION":
            continue
        if edge.get("source") == track_id:
            ids.add(edge["target"])
            matched_people.add(edge["target"])
        elif edge.get("target") == track_id:
            ids.add(edge["source"])
            matched_people.add(edge["source"])

    for edge in data.get("edges", []):
        if edge.get("relation") not in {"ADVISES", "AT_SCHOOL"}:
            continue
        if edge.get("source") in matched_people or edge.get("target") in matched_people:
            ids.add(edge["source"])
            ids.add(edge["target"])

    result = _subgraph(data, ids)
    result["query"] = {"type": "direction", "direction": direction_key}
    result["summary"] = summarize_subgraph(result)
    return result


def professor_subgraph(name: str, path: str | Path = GRAPH_JSON) -> dict:
    data = load_graph(path)
    q = (name or "").strip().lower()
    if not q:
        raise ValueError("professor name is required")

    nodes, edges, _labels = _index(data)
    matched = {
        node_id for node_id, node in nodes.items()
        if node.get("type") == "pi" and q in node.get("label", "").lower()
    }
    ids = set(matched)

    for edge in edges:
        if edge.get("source") in matched or edge.get("target") in matched:
            if edge.get("relation") in {"ADVISES", "AT_SCHOOL", "MATCHES_DIRECTION"}:
                ids.add(edge["source"])
                ids.add(edge["target"])

    result = _subgraph(data, ids)
    result["query"] = {"type": "professor", "name": name}
    result["summary"] = summarize_subgraph(result)
    return result


def summarize_subgraph(data: dict) -> dict:
    counts = {}
    for node in data.get("nodes", []):
        typ = node.get("type", "unknown")
        counts[typ] = counts.get(typ, 0) + 1
    relation_counts = {}
    for edge in data.get("edges", []):
        rel = edge.get("relation", "unknown")
        relation_counts[rel] = relation_counts.get(rel, 0) + 1
    return {
        "nodes": len(data.get("nodes", [])),
        "edges": len(data.get("edges", [])),
        "node_types": dict(sorted(counts.items())),
        "edge_types": dict(sorted(relation_counts.items())),
    }


def refresh_graph(max_labs_per_track: int = 10, max_students_per_lab: int = 6) -> dict:
    return export_world_model_graph(
        max_labs_per_track=max_labs_per_track,
        max_students_per_lab=max_students_per_lab,
        out_dir=EXPORTS_DIR,
    )

