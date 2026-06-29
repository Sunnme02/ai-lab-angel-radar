"""Export a focused graph for any AI direction.

This is the generic version of the direction search graph:
direction -> professors -> students, with schools as context. Papers are kept as
evidence on edges instead of becoming graph nodes, which keeps the output usable
for open-ended direction searches such as Agent, AI Infra or World Model.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import sqlite3
from collections import Counter
from pathlib import Path

from .export_world_model_graph import (
    DB_PATH,
    DISPLAY_COLORS,
    DISPLAY_TYPES,
    EXPORTS_DIR,
    Graph,
    clean_cell,
    load_scores,
    write_graphml,
    write_json,
)

LEGEND_ITEMS = [
    ("direction", "方向"),
    ("professor", "教授"),
    ("student", "学生"),
    ("school", "学校/机构"),
]


def slugify(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", (text or "").strip().lower())
    return value.strip("_") or "direction"


def parse_keywords(direction: str, keywords: str = "") -> list[str]:
    raw = [direction]
    raw.extend(re.split(r"[,;，；\n]+", keywords or ""))
    seen = set()
    out = []
    for item in raw:
        item = re.sub(r"\s+", " ", item or "").strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _is_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _usable_keyword(keyword: str) -> bool:
    compact = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "", keyword or "")
    return len(compact) >= 3 or _is_cjk(compact)


def find_hits(text: str, keywords: list[str]) -> list[str]:
    text = text or ""
    hits = []
    for keyword in keywords:
        if not _usable_keyword(keyword):
            continue
        pattern = re.escape(keyword).replace(r"\ ", r"[-\s]+")
        if re.search(pattern, text, re.I):
            hits.append(keyword)
    return list(dict.fromkeys(hits))


def match_lab(lab: sqlite3.Row, papers: list[sqlite3.Row], keywords: list[str], lab_score: float):
    lab_text = " ".join(
        clean_cell(lab[key])
        for key in ("lab_name", "pi_name", "pi_name_cn", "keywords")
        if key in lab.keys()
    )
    lab_hits = find_hits(lab_text, keywords)
    score = 0.0
    evidence = []
    paper_count = 0
    citations = 0

    if lab_hits:
        score += 6 + len(lab_hits) * 1.5
        evidence.append("Lab keywords: " + ", ".join(lab_hits[:5]))

    for paper in papers:
        title = clean_cell(paper["title"])
        title_hits = find_hits(title, keywords)
        full_text = " ".join(
            clean_cell(paper[key])
            for key in ("title", "keywords_matched", "venue")
            if key in paper.keys()
        )
        hits = find_hits(full_text, keywords)
        if not hits and not title_hits:
            continue
        paper_count += 1
        citations += paper["citation_count"] or 0
        title_bonus = 4 if title_hits else 0
        score += 2 + title_bonus + min(math.log1p(paper["citation_count"] or 0), 5)
        if title and title not in evidence and len(evidence) < 6:
            evidence.append(title)

    if score <= 0:
        return None
    score += min(float(lab_score or 0) / 20, 5)
    return {
        "score": score,
        "paper_count": paper_count,
        "citations": citations,
        "evidence": evidence,
        "lab_hits": lab_hits,
    }


def _add_person_node(graph: Graph, person_id: str, label: str, *, typ="person", title="", score=0, size=14):
    if person_id in graph.nodes:
        size = max(float(graph.nodes[person_id].get("size", 0) or 0), float(size or 0))
        if graph.nodes[person_id].get("type") == "pi" or typ == "pi":
            typ = "pi"
    graph.add_node(person_id, type=typ, label=label, title=title or label, score=score or "", size=size)


def build_direction_graph(
    direction: str,
    keywords: list[str],
    *,
    max_labs: int = 12,
    max_students_per_lab: int = 6,
    min_confidence: float = 0.5,
):
    graph = Graph()
    direction_id = f"direction:{slugify(direction)}"
    graph.add_node(direction_id, type="direction", label=direction, title=", ".join(keywords), size=42)

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    lab_scores = load_scores(con, "lab", "angel_radar_score")
    person_scores = load_scores(con, "person", "student_startup_score")
    lab_pi_names = {
        row["pi_name"]
        for row in con.execute("select pi_name from labs where pi_name is not null").fetchall()
    }

    candidates = []
    for lab in con.execute("select * from labs").fetchall():
        papers = con.execute("select * from papers where lab_id=?", (lab["id"],)).fetchall()
        stats = match_lab(lab, papers, keywords, lab_scores.get(lab["id"], 0))
        if stats:
            candidates.append((stats["score"], lab, stats))
    candidates.sort(key=lambda item: item[0], reverse=True)

    selected = candidates[:max_labs]
    for score, lab, stats in selected:
        pi = con.execute(
            "select * from people where is_pi=1 and name=? limit 1",
            (lab["pi_name"],),
        ).fetchone()
        if pi:
            pi_node = f"person:{pi['id']}"
            pi_score = person_scores.get(pi["id"], 0)
            pi_id_for_edges = pi["id"]
        else:
            pi_node = f"person:lab-pi:{lab['id']}"
            pi_score = lab_scores.get(lab["id"], 0)
            pi_id_for_edges = None

        evidence = "; ".join(stats["evidence"][:4])
        title = f"{lab['school'] or ''} / {lab['lab_name'] or lab['pi_name']}"
        if evidence:
            title += f" | 方向证据: {evidence}"
        _add_person_node(
            graph,
            pi_node,
            lab["pi_name"],
            typ="pi",
            title=title,
            score=pi_score,
            size=24 + min(float(score or 0), 20),
        )

        if lab["school"]:
            school_node = f"school:{lab['school']}"
            graph.add_node(school_node, type="school", label=lab["school"], size=24)
            graph.add_edge(school_node, pi_node, "AT_SCHOOL", weight=2)

        edge_title = f"{direction} · {stats['paper_count']} 条方向证据"
        if evidence:
            edge_title += ": " + evidence
        graph.add_edge(
            direction_id,
            pi_node,
            "MATCHES_DIRECTION",
            weight=2 + min(score / 6, 6),
            title=edge_title,
            count=stats["paper_count"],
        )

        if not pi_id_for_edges:
            continue

        advisors = con.execute(
            """
            select r.confidence, pe.*
            from relationships r join people pe on pe.id = r.target_id
            where r.relation_type='ADVISES'
              and r.source_id=?
              and r.confidence >= ?
            order by r.confidence desc
            limit ?
            """,
            (pi_id_for_edges, min_confidence, max_students_per_lab * 3),
        ).fetchall()
        added = 0
        for student in advisors:
            if student["is_pi"] or student["name"] in lab_pi_names:
                continue
            if added >= max_students_per_lab:
                break
            student_node = f"person:{student['id']}"
            stu_score = person_scores.get(student["id"], 0)
            _add_person_node(
                graph,
                student_node,
                student["name"],
                typ="person",
                title=student["affiliation"] or student["name"],
                score=stu_score,
                size=10 + min(float(stu_score or 0) / 6, 16),
            )
            graph.add_edge(
                pi_node,
                student_node,
                "ADVISES",
                confidence=student["confidence"],
                weight=1 + float(student["confidence"] or 0) * 3,
                title=f"导师/学生关系 · confidence {student['confidence']:.2f}",
            )
            added += 1

    con.close()
    meta = {
        "name": "Generic AI Direction Graph",
        "direction": direction,
        "keywords": keywords,
        "matched_labs": len(candidates),
        "shown_labs": len(selected),
        "max_labs": max_labs,
        "max_students_per_lab": max_students_per_lab,
        "db_path": str(DB_PATH),
    }
    meta.update(summarize(graph))
    return graph, meta


def summarize(graph: Graph):
    node_types = Counter(node.get("type", "?") for node in graph.nodes.values())
    edge_types = Counter(edge.get("relation", "?") for edge in graph.edges.values())
    return {
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "node_types": dict(sorted(node_types.items())),
        "edge_types": dict(sorted(edge_types.items())),
    }


def write_html(graph: Graph, path: Path, meta: dict):
    data = graph.as_dict(meta)
    for node in data["nodes"]:
        display_type, display_label = DISPLAY_TYPES.get(node.get("type"), (node.get("type", "other"), "其他"))
        node["displayType"] = display_type
        node["displayLabel"] = display_label
        node["color"] = DISPLAY_COLORS.get(display_type, "#9ca3af")
        node["shape"] = "dot"
        node["value"] = node.get("size", 12)
        title_bits = [
            f"<b>{html.escape(str(node.get('label', node['id'])))}</b>",
            html.escape(display_label),
        ]
        for key in ("title", "score", "url"):
            if node.get(key):
                value = html.escape(str(node[key]))
                title_bits.append(f"{key}: {value}")
        node["title"] = "<br>".join(title_bits)

    for edge in data["edges"]:
        edge["from"] = edge.pop("source")
        edge["to"] = edge.pop("target")
        edge["title"] = edge.get("title") or edge.get("relation", "")
        edge["width"] = float(edge.get("weight", 1) or 1)
        edge["length"] = {"ADVISES": 95, "AT_SCHOOL": 240, "MATCHES_DIRECTION": 220}.get(edge.get("relation"), 160)

    graph_json = json.dumps(data, ensure_ascii=False)
    legend = "".join(
        f'<div><span style="background:{DISPLAY_COLORS[key]}"></span>{label}</div>'
        for key, label in LEGEND_ITEMS
    )
    vis_path = Path(__file__).resolve().parents[2] / "lib" / "vis-9.1.2" / "vis-network.min.js"
    if vis_path.exists():
        vis_script = vis_path.read_text(encoding="utf-8").replace("</script>", "<\\/script>")
        vis_loader = f"<script>{vis_script}</script>"
    else:
        vis_loader = '<script src="../../lib/vis-9.1.2/vis-network.min.js"></script>'

    title = html.escape(meta["direction"])
    keywords = html.escape(", ".join(meta["keywords"]))
    html_doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>{title} Direction Graph</title>
  <link rel="stylesheet" href="../../lib/vis-9.1.2/vis-network.css"/>
  {vis_loader}
  <style>
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    #graph {{ width:100vw; height:100vh; }}
    #panel {{
      position:fixed; left:16px; top:16px; z-index:10; width:360px;
      background:rgba(255,255,255,.94); border:1px solid #d1d5db; border-radius:8px;
      box-shadow:0 8px 30px rgba(15,23,42,.16); padding:12px 14px;
    }}
    h1 {{ font-size:18px; margin:0 0 6px; }}
    .meta {{ color:#475569; font-size:13px; line-height:1.45; }}
    .legend {{ display:grid; grid-template-columns:1fr 1fr; gap:5px 12px; margin-top:10px; font-size:13px; }}
    .legend span {{ display:inline-block; width:11px; height:11px; border-radius:50%; margin-right:6px; }}
    input {{ width:100%; box-sizing:border-box; margin-top:10px; padding:8px 9px; border:1px solid #cbd5e1; border-radius:6px; font-size:13px; }}
    button {{ margin-top:8px; padding:7px 9px; border:1px solid #cbd5e1; background:#f8fafc; border-radius:6px; cursor:pointer; font-size:13px; }}
  </style>
</head>
<body>
  <div id="panel">
    <h1>{title} Direction Graph</h1>
    <div class="meta">
      Nodes: {len(graph.nodes)} · Edges: {len(graph.edges)}<br/>
      Labs: {meta['shown_labs']} shown / {meta['matched_labs']} matched<br/>
      Keywords: {keywords}
    </div>
    <input id="search" placeholder="搜索姓名、学校或方向证据..."/>
    <button onclick="fitGraph()">适配画面</button>
    <div class="legend">{legend}</div>
  </div>
  <div id="graph"></div>
  <script>
    const data = {graph_json};
    const originalNodes = data.nodes.map(n => ({{...n}}));
    const originalEdges = data.edges.map(e => ({{...e}}));
    const nodes = new vis.DataSet(data.nodes);
    const edges = new vis.DataSet(data.edges);
    const network = new vis.Network(document.getElementById('graph'), {{nodes, edges}}, {{
      physics: {{ stabilization: {{iterations: 220}}, barnesHut: {{ gravitationalConstant: -26000, springLength: 170 }} }},
      interaction: {{ hover: true, tooltipDelay: 80 }},
      nodes: {{ font: {{ size: 13, face: '-apple-system, Segoe UI, sans-serif', strokeWidth: 3 }} }},
      edges: {{ color: {{ color: '#94a3b8', highlight: '#334155' }}, smooth: {{ type: 'dynamic' }}, font: {{ size: 0 }} }}
    }});
    function fitGraph() {{ network.fit({{ animation: true }}); }}
    function applyFilters() {{
      const q = document.getElementById('search').value.toLowerCase().trim();
      const matched = originalNodes.filter(n => {{
        const text = ((n.label || '') + ' ' + (n.title || '') + ' ' + (n.displayLabel || '')).toLowerCase();
        return !q || text.includes(q);
      }});
      const keep = new Set(matched.map(n => n.id));
      const filteredEdges = originalEdges.filter(e => keep.has(e.from) && keep.has(e.to));
      nodes.clear();
      edges.clear();
      nodes.add(matched);
      edges.add(filteredEdges);
    }}
    document.getElementById('search').addEventListener('input', applyFilters);
    window.fitGraph = fitGraph;
  </script>
</body>
</html>"""
    path.write_text(html_doc, encoding="utf-8")


def export_direction_graph(
    direction: str,
    keywords: str = "",
    *,
    max_labs: int = 12,
    max_students_per_lab: int = 6,
    out_dir: str | Path = EXPORTS_DIR,
):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    parsed_keywords = parse_keywords(direction, keywords)
    graph, meta = build_direction_graph(
        direction,
        parsed_keywords,
        max_labs=max_labs,
        max_students_per_lab=max_students_per_lab,
    )
    slug = slugify(direction)
    json_path = out_dir / f"direction_graph_{slug}.json"
    html_path = out_dir / f"direction_graph_{slug}.html"
    graphml_path = out_dir / f"direction_graph_{slug}.graphml"
    write_json(graph, json_path, meta)
    write_graphml(graph, graphml_path)
    write_html(graph, html_path, meta)
    write_json(graph, out_dir / "direction_graph.json", meta)
    write_graphml(graph, out_dir / "direction_graph.graphml")
    write_html(graph, out_dir / "direction_graph.html", meta)
    return {"json": str(json_path), "html": str(html_path), "graphml": str(graphml_path), **meta}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--direction", required=True)
    parser.add_argument("--keywords", default="")
    parser.add_argument("--max-labs", type=int, default=12)
    parser.add_argument("--max-students-per-lab", type=int, default=6)
    parser.add_argument("--out-dir", default=str(EXPORTS_DIR))
    args = parser.parse_args()
    meta = export_direction_graph(
        args.direction,
        args.keywords,
        max_labs=args.max_labs,
        max_students_per_lab=args.max_students_per_lab,
        out_dir=args.out_dir,
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

