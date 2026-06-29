"""Export a professor-centered radial ego graph.

The layout is intentionally deterministic: professor in the center, students on
one ring, professor-student edges weighted by advising confidence plus coauthor
evidence, and student-student edges weighted by coauthored papers.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "radar.db"
EXPORTS_DIR = ROOT / "data" / "exports"


def slugify(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", (text or "").strip().lower())
    return value.strip("_") or "professor"


def load_scores(con: sqlite3.Connection, entity_type: str, score_name: str):
    rows = con.execute(
        "select entity_id, score_value from scores where entity_type=? and score_name=?",
        (entity_type, score_name),
    ).fetchall()
    return {row["entity_id"]: row["score_value"] for row in rows}


def pick_pi(con: sqlite3.Connection, pi_name: str):
    lab = con.execute("select * from labs where pi_name=? limit 1", (pi_name,)).fetchone()
    if lab and lab["school"]:
        pi = con.execute(
            """
            select * from people
            where is_pi=1 and name=? and coalesce(affiliation, '') like ?
            limit 1
            """,
            (pi_name, f"%{lab['school']}%"),
        ).fetchone()
        if pi:
            return lab, pi
    pi = con.execute("select * from people where is_pi=1 and name=? limit 1", (pi_name,)).fetchone()
    return lab, pi


def coauthor_edges(con: sqlite3.Connection, person_ids: list[int], max_evidence: int = 4):
    if not person_ids:
        return {}
    placeholders = ",".join("?" for _ in person_ids)
    rows = con.execute(
        f"""
        select a.paper_id, a.person_id, p.title, coalesce(p.citation_count, 0) as citations
        from authorships a join papers p on p.id = a.paper_id
        where a.person_id in ({placeholders})
        """,
        person_ids,
    ).fetchall()
    paper_people = defaultdict(list)
    paper_titles = {}
    paper_citations = {}
    for row in rows:
        paper_people[row["paper_id"]].append(row["person_id"])
        paper_titles[row["paper_id"]] = row["title"] or f"paper:{row['paper_id']}"
        paper_citations[row["paper_id"]] = row["citations"] or 0

    edges = {}
    for paper_id, ids in paper_people.items():
        unique = sorted(set(ids))
        if len(unique) < 2:
            continue
        for i, source in enumerate(unique):
            for target in unique[i + 1:]:
                key = (source, target)
                cur = edges.setdefault(key, {"count": 0, "citations": 0, "evidence": []})
                cur["count"] += 1
                cur["citations"] += paper_citations[paper_id]
                if len(cur["evidence"]) < max_evidence:
                    cur["evidence"].append(paper_titles[paper_id])
    return edges


def build_pi_ego(pi_name: str, max_students: int = 16, min_confidence: float = 0.5):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    person_scores = load_scores(con, "person", "student_startup_score")
    lab_pi_names = {
        row["pi_name"]
        for row in con.execute("select pi_name from labs where pi_name is not null").fetchall()
    }

    lab, pi = pick_pi(con, pi_name)
    if not pi:
        con.close()
        raise ValueError(f"Cannot find PI named {pi_name!r}")

    rows = con.execute(
        """
        select r.confidence, pe.*
        from relationships r join people pe on pe.id = r.target_id
        where r.relation_type='ADVISES'
          and r.source_id=?
          and r.confidence >= ?
        order by r.confidence desc
        limit ?
        """,
        (pi["id"], min_confidence, max_students * 4),
    ).fetchall()

    students = []
    seen_names = set()
    for row in rows:
        if row["is_pi"] or row["name"] in lab_pi_names:
            continue
        key = (row["name"] or "").strip().lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        students.append(row)
        if len(students) >= max_students:
            break

    ids = [pi["id"]] + [student["id"] for student in students]
    coauthors = coauthor_edges(con, ids)

    nodes = [
        {
            "id": f"person:{pi['id']}",
            "person_id": pi["id"],
            "type": "pi",
            "label": pi["name"],
            "score": person_scores.get(pi["id"], 0),
            "school": lab["school"] if lab else pi["affiliation"],
            "lab": lab["lab_name"] if lab else "",
        }
    ]
    for student in students:
        nodes.append(
            {
                "id": f"person:{student['id']}",
                "person_id": student["id"],
                "type": "student",
                "label": student["name"],
                "score": person_scores.get(student["id"], 0),
                "affiliation": student["affiliation"] or "",
            }
        )

    edges = []
    for student in students:
        key = tuple(sorted((pi["id"], student["id"])))
        coop = coauthors.get(key, {"count": 0, "citations": 0, "evidence": []})
        confidence = float(student["confidence"] or 0)
        strength = confidence * 2 + min(coop["count"], 8)
        edges.append(
            {
                "source": f"person:{pi['id']}",
                "target": f"person:{student['id']}",
                "relation": "ADVISES_AND_COLLABORATES",
                "confidence": confidence,
                "coauthored_papers": coop["count"],
                "strength": strength,
                "evidence": coop["evidence"],
            }
        )

    student_ids = {student["id"] for student in students}
    for (source, target), coop in coauthors.items():
        if source not in student_ids or target not in student_ids:
            continue
        edges.append(
            {
                "source": f"person:{source}",
                "target": f"person:{target}",
                "relation": "STUDENT_COAUTHOR",
                "coauthored_papers": coop["count"],
                "strength": min(coop["count"], 8),
                "evidence": coop["evidence"],
            }
        )

    con.close()
    return {
        "meta": {
            "name": "Professor Ego Star Graph",
            "pi_name": pi["name"],
            "school": lab["school"] if lab else pi["affiliation"],
            "lab": lab["lab_name"] if lab else "",
            "max_students": max_students,
            "students": len(students),
            "edges": len(edges),
        },
        "nodes": nodes,
        "edges": edges,
    }


def _node_radius(node):
    if node["type"] == "pi":
        return 46
    return 16 + min(float(node.get("score") or 0) / 8, 18)


def _student_color(score):
    score = float(score or 0)
    if score >= 60:
        return "#0f7a37"
    if score >= 35:
        return "#55b567"
    if score >= 15:
        return "#b8d5aa"
    return "#f2f3ee"


def write_json(data: dict, path: Path):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_html(data: dict, path: Path):
    width, height = 1440, 980
    cx, cy = width / 2, height / 2
    ring = 330
    nodes = data["nodes"]
    edges = data["edges"]
    positions = {}
    positions[nodes[0]["id"]] = (cx, cy)

    students = [node for node in nodes if node["type"] == "student"]
    for idx, node in enumerate(students):
        angle = -math.pi / 2 + idx * (2 * math.pi / max(len(students), 1))
        positions[node["id"]] = (cx + ring * math.cos(angle), cy + ring * math.sin(angle))

    node_by_id = {node["id"]: node for node in nodes}

    def line(edge):
        x1, y1 = positions[edge["source"]]
        x2, y2 = positions[edge["target"]]
        strength = float(edge.get("strength") or 1)
        if edge["relation"] == "STUDENT_COAUTHOR":
            width_px = 0.8 + min(strength * 1.35, 9)
            color = "#8b8fa3"
            opacity = 0.16 + min(strength / 12, 0.42)
        else:
            width_px = 1.4 + min(strength * 1.15, 10)
            color = "#4c1d95"
            opacity = 0.28 + min(strength / 12, 0.55)
        evidence = "; ".join(edge.get("evidence") or [])
        title = (
            f"{edge['relation']} | strength={strength:.2f} | "
            f"coauthored_papers={edge.get('coauthored_papers', 0)}"
        )
        if evidence:
            title += f" | {evidence}"
        return (
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{width_px:.2f}" stroke-opacity="{opacity:.2f}" '
            f'stroke-linecap="round"><title>{html.escape(title)}</title></line>'
        )

    def circle(node):
        x, y = positions[node["id"]]
        r = _node_radius(node)
        if node["type"] == "pi":
            fill = "#0b5d2a"
            stroke = "#062814"
            label_y = y + r + 24
            weight = 700
        else:
            fill = _student_color(node.get("score"))
            stroke = "#1f2937"
            label_y = y + r + 18
            weight = 600
        title_bits = [
            node.get("label", ""),
            f"type: {node['type']}",
            f"score: {node.get('score', 0)}",
        ]
        if node.get("affiliation"):
            title_bits.append(f"affiliation: {node['affiliation']}")
        if node.get("school"):
            title_bits.append(f"school: {node['school']}")
        return "\n".join(
            [
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" '
                f'stroke="{stroke}" stroke-width="2.4"><title>{html.escape(" | ".join(title_bits))}</title></circle>',
                f'<text x="{x:.1f}" y="{label_y:.1f}" text-anchor="middle" '
                f'font-size="{15 if node["type"] == "pi" else 13}" '
                f'font-weight="{weight}" fill="#111827">{html.escape(node["label"])}</text>',
            ]
        )

    svg_edges = "\n".join(line(edge) for edge in sorted(edges, key=lambda e: e["relation"] == "ADVISES_AND_COLLABORATES"))
    svg_nodes = "\n".join(circle(node) for node in nodes)
    meta = data["meta"]
    pi_label = html.escape(meta["pi_name"])
    subtitle = html.escape(f"{meta.get('school') or ''} · {meta.get('lab') or ''}")
    html_doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>{pi_label} Ego Star Graph</title>
  <style>
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:#111827; }}
    .panel {{
      position:fixed; left:18px; top:18px; width:330px; z-index:5;
      background:rgba(255,255,255,.94); border:1px solid #d1d5db; border-radius:8px;
      padding:14px 16px; box-shadow:0 12px 34px rgba(15,23,42,.16);
    }}
    h1 {{ margin:0 0 6px; font-size:18px; }}
    .meta {{ color:#475569; font-size:13px; line-height:1.45; }}
    .legend {{ display:grid; grid-template-columns:1fr; gap:6px; margin-top:12px; font-size:13px; }}
    .swatch {{ display:inline-block; width:38px; height:7px; border-radius:99px; margin-right:8px; vertical-align:middle; }}
    svg {{ width:100vw; height:100vh; background:#fbfbf8; }}
  </style>
</head>
<body>
  <div class="panel">
    <h1>{pi_label} 恒星图</h1>
    <div class="meta">
      {subtitle}<br/>
      Students: {meta["students"]} · Edges: {meta["edges"]}<br/>
      点越绿代表学生分数越高；线越粗代表合作/关系越强。
    </div>
    <div class="legend">
      <div><span class="swatch" style="background:#0b5d2a"></span>中心：老师</div>
      <div><span class="swatch" style="background:linear-gradient(90deg,#f2f3ee,#55b567,#0f7a37)"></span>学生潜力分</div>
      <div><span class="swatch" style="background:#4c1d95"></span>紫线：老师-学生合作/指导</div>
      <div><span class="swatch" style="background:#8b8fa3"></span>灰线：学生-学生共同论文</div>
    </div>
  </div>
  <svg viewBox="0 0 {width} {height}" role="img" aria-label="{pi_label} ego graph">
    {svg_edges}
    {svg_nodes}
  </svg>
</body>
</html>"""
    path.write_text(html_doc, encoding="utf-8")


def export_pi_ego_graph(pi_name: str, max_students: int = 16, out_dir: str | Path = EXPORTS_DIR):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = build_pi_ego(pi_name, max_students=max_students)
    slug = slugify(pi_name)
    json_path = out_dir / f"pi_ego_{slug}.json"
    html_path = out_dir / f"pi_ego_{slug}.html"
    write_json(data, json_path)
    write_html(data, html_path)
    write_json(data, out_dir / "pi_ego_graph.json")
    write_html(data, out_dir / "pi_ego_graph.html")
    return {"json": str(json_path), "html": str(html_path), **data["meta"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pi", default="Fuchun Sun")
    parser.add_argument("--max-students", type=int, default=16)
    parser.add_argument("--out-dir", default=str(EXPORTS_DIR))
    args = parser.parse_args()
    meta = export_pi_ego_graph(args.pi, max_students=args.max_students, out_dir=args.out_dir)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
