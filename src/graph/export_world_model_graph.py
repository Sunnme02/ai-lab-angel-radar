"""Export a focused World Model knowledge graph.

This script intentionally uses only the Python standard library so the graph can
be regenerated even before the full project environment is installed.

Outputs:
  data/exports/world_model_graph.json
  data/exports/world_model_graph.graphml
  data/exports/world_model_graph.html
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import sqlite3
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT.parent
DB_PATH = ROOT / "data" / "radar.db"
EXPORTS_DIR = ROOT / "data" / "exports"

PAPER_FILES = [
    WORKSPACE / "ml_cn_papers" / "output" / "ml_cn_papers.xlsx",
    WORKSPACE / "ml_cn_papers" / "output" / "cvpr2025_cn.xlsx",
    WORKSPACE / "ml_cn_papers" / "output" / "一作清北_大牛与分类.xlsx",
]

NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

TRACKS = {
    "core": {
        "label": "Core World Models",
        "patterns": [
            r"\bworld\s*models?\b",
            r"\bworld[- ]model(?:ing)?\b",
            r"\bworld\s+modeling\b",
            r"\bworld\s+simulators?\b",
            r"\bworld\s+foundation\b",
            r"\blatent\s+dynamics\b",
            r"\bmodel[- ]based\s+(reinforcement\s+learning|rl)\b",
            r"\bworld[- ]action\s+model\b",
            r"\bworld[- ]aware\b",
        ],
    },
    "embodied": {
        "label": "Embodied / Robot World Models",
        "patterns": [
            r"\bvision[- ]language[- ]action\b",
            r"\bVLA\b",
            r"\bembodied\s+(ai|agent|intelligence|reasoning|future)\b",
            r"\brobot(ic)?\s+manipulation\b",
            r"\brobot(ic)?\s+grasping\b",
            r"\brobot\s+learning\b",
            r"\brobot(ic|ics)?\s+foundation\b",
            r"\bsim2real\b",
            r"\bsim-to-real\b",
            r"\bdexterous\b",
            r"\bhumanoid\b",
            r"\binteractive\s+video\s+generation\b",
            r"\bvideo\s+diffusion\b",
            r"\bvideo\s+world\s+model\b",
        ],
    },
    "driving": {
        "label": "Driving / 4D Scene Models",
        "patterns": [
            r"\bautonomous\s+driving\b",
            r"\bdriving\s+(world|scene|planning|simulation)\b",
            r"\boccupancy\s+prediction\b",
            r"\b3d\s+occupancy\b",
            r"\b4d\s+(world|driving|scene|generation|modeling)\b",
            r"\btrajectory\s+world\s+models?\b",
            r"\bdriving\s+(trajectory|planning|closed[- ]loop)\b",
            r"\b(trajectory|planning|closed[- ]loop)\s+(for\s+)?(autonomous\s+)?driving\b",
        ],
    },
}

EXCLUDE_PATTERNS = [
    r"\bsmall[- ]world\s+graphs?\b",
    r"\bpower\s+grid\b",
    r"\bwireless\s+communications?\b",
]

NODE_COLORS = {
    "direction": "#111827",
    "track": "#f59e0b",
    "keyword": "#facc15",
    "paper": "#94a3b8",
    "lab": "#ef4444",
    "pi": "#f97316",
    "person": "#3b82f6",
    "institution": "#64748b",
    "school": "#475569",
    "repo": "#22c55e",
    "source": "#a855f7",
}

DISPLAY_TYPES = {
    "direction": ("direction", "方向"),
    "track": ("direction", "方向"),
    "keyword": ("direction", "方向"),
    "paper": ("paper", "论文"),
    "lab": ("person", "人"),
    "pi": ("professor", "教授"),
    "person": ("student", "学生"),
    "institution": ("school", "学校/机构"),
    "school": ("school", "学校/机构"),
    "repo": ("repo", "项目"),
    "source": ("source", "来源"),
}

DISPLAY_COLORS = {
    "direction": "#f59e0b",
    "paper": "#94a3b8",
    "person": "#3b82f6",
    "professor": "#f97316",
    "student": "#2563eb",
    "school": "#475569",
    "repo": "#22c55e",
    "source": "#a855f7",
}

LEGEND_ITEMS = [
    ("direction", "方向"),
    ("professor", "教授"),
    ("student", "学生"),
    ("school", "学校/机构"),
]


def norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (title or "").lower())


def short_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:14]


def clean_cell(value) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").strip()


def classify(text: str) -> tuple[str | None, list[str]]:
    if re.search(r"\bsmall[- ]world\b", text or "", re.I) and not re.search(
        r"\bworld[- ]?models?\b|\bworld\s+modeling\b", text or "", re.I
    ):
        return None, []
    found = []
    for track, spec in TRACKS.items():
        for pattern in spec["patterns"]:
            if re.search(pattern, text or "", re.I):
                found.append(track)
                break
    if not found:
        return None, []
    # Keep explicit world-model papers even when they also mention broad noise words.
    if "core" not in found:
        for pattern in EXCLUDE_PATTERNS:
            if re.search(pattern, text or "", re.I):
                return None, []
    priority = ["core", "embodied", "driving"]
    primary = min(found, key=priority.index)
    return primary, found


def skip_noisy_world_title(title: str) -> bool:
    return bool(
        re.search(r"\bsmall[- ]world\b", title or "", re.I)
        and not re.search(
            r"\bworld[- ]?models?\b|\bworld\s+modeling\b|\bworld\s+simulators?\b",
            title or "",
            re.I,
        )
    )


class Graph:
    def __init__(self):
        self.nodes = {}
        self.edges = {}

    def add_node(self, node_id: str, **attrs):
        cur = self.nodes.setdefault(node_id, {"id": node_id})
        for key, value in attrs.items():
            if value not in (None, ""):
                cur[key] = value

    def add_edge(self, source: str, target: str, relation: str, **attrs):
        if source == target:
            return
        key = (source, target, relation)
        cur = self.edges.setdefault(key, {"source": source, "target": target, "relation": relation})
        for attr, value in attrs.items():
            if value not in (None, ""):
                cur[attr] = value

    def as_dict(self, meta=None):
        return {
            "meta": meta or {},
            "nodes": [dict(node) for node in self.nodes.values()],
            "edges": [dict(edge) for edge in self.edges.values()],
        }


def col_to_num(col: str) -> int:
    num = 0
    for ch in col:
        num = num * 26 + ord(ch) - 64
    return num


def read_xlsx(path: Path):
    if not path.exists():
        return
    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("main:si", NS):
                shared.append(
                    "".join(
                        t.text or ""
                        for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                    )
                )

        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
        sheet = wb.find("main:sheets", NS)[0]
        rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = rid_to_target[rid].lstrip("/")
        sheet_path = target if target.startswith("xl/") else "xl/" + target
        ws = ET.fromstring(zf.read(sheet_path))

        for row in ws.findall("main:sheetData/main:row", NS):
            vals = {}
            for cell in row.findall("main:c", NS):
                ref = cell.attrib.get("r", "")
                match = re.match(r"([A-Z]+)", ref)
                if not match:
                    continue
                idx = col_to_num(match.group(1)) - 1
                typ = cell.attrib.get("t")
                value = ""
                v = cell.find("main:v", NS)
                if typ == "s" and v is not None and v.text:
                    value = shared[int(v.text)]
                elif typ == "inlineStr":
                    value = "".join(
                        t.text or ""
                        for t in cell.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                    )
                elif v is not None:
                    value = v.text or ""
                vals[idx] = clean_cell(value)
            if vals:
                yield [vals.get(i, "") for i in range(max(vals) + 1)]


def add_base_nodes(graph: Graph):
    graph.add_node(
        "direction:world_model",
        type="direction",
        label="World Model",
        title="世界模型方向",
        size=42,
    )
    for key, spec in TRACKS.items():
        node = f"track:{key}"
        graph.add_node(node, type="track", label=spec["label"], size=28)
        graph.add_edge("direction:world_model", node, "HAS_TRACK", weight=4)


def add_keyword_nodes(graph: Graph, paper_node: str, tracks: list[str]):
    for track in tracks:
        node = f"keyword:{track}"
        graph.add_node(node, type="keyword", label=TRACKS[track]["label"], size=18)
        graph.add_edge(paper_node, node, "HAS_SIGNAL", weight=2)


def add_paper(
    graph: Graph,
    title: str,
    source: str,
    primary_track: str,
    tracks: list[str],
    *,
    year="",
    venue="",
    url="",
    institution="",
    authors="",
    first_author_inst="",
    citation_count=0,
):
    if re.search(r"\bsmall[- ]world\b", title or "", re.I):
        return None
    key = norm_title(title)
    if not key:
        return None
    node = f"paper:{short_hash(key)}"
    label = title[:80]
    size = 12 + min(int(citation_count or 0) ** 0.5, 18)
    graph.add_node(
        node,
        type="paper",
        label=label,
        title=title,
        year=year,
        venue=venue,
        url=url,
        source=source,
        category=primary_track,
        citations=citation_count or "",
        authors=authors[:500],
        size=size,
    )
    graph.add_edge(f"track:{primary_track}", node, "HAS_PAPER", weight=3)
    add_keyword_nodes(graph, node, tracks)

    inst_label = first_author_inst or institution
    if inst_label:
        inst = re.split(r";|；", inst_label)[0].strip()
        inst = re.sub(r"\(.+?\)", "", inst).strip()
        if inst:
            inst_node = f"institution:{short_hash(inst.lower())}"
            graph.add_node(inst_node, type="institution", label=inst[:70], title=inst, size=18)
            graph.add_edge(inst_node, node, "AFFILIATED_WITH", weight=2)
    return node


def load_scores(con: sqlite3.Connection, entity_type: str, score_name: str):
    rows = con.execute(
        "select entity_id, score_value from scores where entity_type=? and score_name=?",
        (entity_type, score_name),
    ).fetchall()
    return {row["entity_id"]: row["score_value"] for row in rows}


def add_radar_db(graph: Graph, max_db_papers: int):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    lab_scores = load_scores(con, "lab", "angel_radar_score")
    person_scores = load_scores(con, "person", "student_startup_score")

    candidates = []
    rows = con.execute(
        """
        select p.*, l.pi_name, l.school, l.id as lab_id, l.keywords as lab_keywords
        from papers p join labs l on l.id = p.lab_id
        """
    ).fetchall()
    for row in rows:
        text = " ".join(clean_cell(row[key]) for key in ["title", "abstract", "venue"])
        primary, tracks = classify(text)
        if not primary:
            continue
        rank = (5 if primary == "core" else 3 if primary in ("embodied", "driving") else 1)
        rank += min((row["citation_count"] or 0) / 30, 5)
        candidates.append((rank, primary, tracks, row))
    candidates.sort(key=lambda item: item[0], reverse=True)
    candidates = candidates[:max_db_papers]

    lab_ids = set()
    paper_ids = []
    for _rank, primary, tracks, row in candidates:
        lab_ids.add(row["lab_id"])
        paper_ids.append(row["id"])
        paper_node = add_paper(
            graph,
            row["title"],
            "radar.db",
            primary,
            tracks,
            year=row["year"],
            venue=row["venue"],
            url=row["url"],
            citation_count=row["citation_count"] or 0,
        )
        if not paper_node:
            continue
        lab_node = f"lab:{row['lab_id']}"
        graph.add_node(
            lab_node,
            type="lab",
            label=f"{row['pi_name']} Lab",
            title=f"{row['school']} / {row['pi_name']}",
            school=row["school"],
            score=lab_scores.get(row["lab_id"], ""),
            size=18 + float(lab_scores.get(row["lab_id"], 0)) / 6,
        )
        graph.add_edge(lab_node, paper_node, "PRODUCED", weight=3)
        if row["school"]:
            school_node = f"school:{row['school']}"
            graph.add_node(school_node, type="school", label=row["school"], size=24)
            graph.add_edge(school_node, lab_node, "HAS_LAB", weight=2)

    for lab_id in lab_ids:
        lab = con.execute("select * from labs where id=?", (lab_id,)).fetchone()
        if not lab:
            continue
        pi = con.execute(
            "select * from people where is_pi=1 and name=? limit 1", (lab["pi_name"],)
        ).fetchone()
        if pi:
            pi_node = f"person:{pi['id']}"
            graph.add_node(pi_node, type="pi", label=pi["name"], score=person_scores.get(pi["id"], ""), size=26)
            graph.add_edge(pi_node, f"lab:{lab_id}", "PI_OF", weight=4)

    if paper_ids:
        placeholders = ",".join("?" for _ in paper_ids)
        authors = con.execute(
            f"""
            select a.paper_id, a.is_first_author, pe.*
            from authorships a join people pe on pe.id = a.person_id
            where a.paper_id in ({placeholders})
              and (a.is_first_author=1 or pe.is_student_candidate=1)
            """,
            paper_ids,
        ).fetchall()
        for row in authors:
            person_node = f"person:{row['id']}"
            ptype = "pi" if row["is_pi"] else "person"
            graph.add_node(
                person_node,
                type=ptype,
                label=row["name"],
                title=row["affiliation"] or row["name"],
                score=person_scores.get(row["id"], ""),
                size=10 + float(person_scores.get(row["id"], 0)) / 7,
            )
            paper = con.execute("select title from papers where id=?", (row["paper_id"],)).fetchone()
            if paper:
                paper_node = f"paper:{short_hash(norm_title(paper['title']))}"
                graph.add_edge(
                    person_node,
                    paper_node,
                    "FIRST_AUTHOR_OF" if row["is_first_author"] else "AUTHOR_OF",
                    weight=3 if row["is_first_author"] else 1,
                )

        person_ids = sorted({row["id"] for row in authors})
        if person_ids:
            placeholders = ",".join("?" for _ in person_ids)
            links = con.execute(
                f"""
                select l.*, r.repo_name, r.owner, r.url, r.stars, r.description
                from person_repo_links l join repos r on r.id = l.repo_id
                where l.person_id in ({placeholders}) and l.confidence >= 0.6
                """,
                person_ids,
            ).fetchall()
            for link in links:
                repo_node = f"repo:{link['repo_id']}"
                graph.add_node(
                    repo_node,
                    type="repo",
                    label=f"{link['owner']}/{link['repo_name']}",
                    title=link["description"] or link["url"],
                    url=link["url"],
                    score=link["stars"] or 0,
                    size=10 + min((link["stars"] or 0) ** 0.5 / 3, 28),
                )
                graph.add_edge(
                    f"person:{link['person_id']}",
                    repo_node,
                    "LINKED_REPO",
                    confidence=link["confidence"],
                    weight=2 + float(link["confidence"] or 0),
                )
    con.close()
    return len(candidates)


def add_excel_papers(graph: Graph, max_excel_papers: int):
    seen = set()
    added = 0
    for path in PAPER_FILES:
        rows = list(read_xlsx(path) or [])
        if not rows:
            continue
        header = rows[0]
        name_to_idx = {name: idx for idx, name in enumerate(header)}

        def get(row, name, default=""):
            idx = name_to_idx.get(name)
            if idx is None or idx >= len(row):
                return default
            return row[idx]

        for row in rows[1:]:
            title = get(row, "文章名字")
            if not title:
                continue
            text = " ".join(row)
            primary, tracks = classify(text)
            if not primary:
                continue
            key = norm_title(title)
            if key in seen:
                continue
            seen.add(key)
            paper_node = add_paper(
                graph,
                title,
                path.name,
                primary,
                tracks,
                year=get(row, "年份"),
                venue=get(row, "会议"),
                url=get(row, "链接"),
                institution=get(row, "所属机构") or get(row, "一作机构"),
                first_author_inst=get(row, "第一作者机构") or get(row, "一作机构"),
                authors=get(row, "作者"),
            )
            if not paper_node:
                continue
            source_node = f"source:{path.stem}"
            graph.add_node(source_node, type="source", label=path.name, size=16)
            graph.add_edge(source_node, paper_node, "CONTAINS", weight=1)
            added += 1
            if added >= max_excel_papers:
                return added
    return added


def split_authors(authors: str) -> list[str]:
    names = []
    for part in re.split(r";|；", authors or ""):
        name = re.sub(r"\s+", " ", part).strip()
        if name and len(name) <= 80:
            names.append(name)
    return names


def person_node_id(name: str) -> str:
    return f"person:name:{short_hash(name.lower())}"


def add_aggregate_edge(graph: Graph, source: str, target: str, relation: str, evidence: str = "", weight=1):
    if not source or not target or source == target:
        return
    if relation in {"COAUTHOR", "SAME_DIRECTION"} and source > target:
        source, target = target, source
    key = (source, target, relation)
    cur = graph.edges.setdefault(
        key,
        {"source": source, "target": target, "relation": relation, "weight": 0, "count": 0, "evidence": []},
    )
    cur["weight"] = min(float(cur.get("weight", 0)) + float(weight or 1), 10)
    cur["count"] = int(cur.get("count", 0)) + 1
    if evidence:
        ev = cur.setdefault("evidence", [])
        if evidence not in ev and len(ev) < 6:
            ev.append(evidence)


def clone_node_for_people_view(out: Graph, node_id: str, attrs: dict, new_type: str | None = None):
    node_type = new_type or attrs.get("type")
    out.add_node(
        node_id,
        type=node_type,
        label=attrs.get("label", node_id),
        title=attrs.get("title", attrs.get("label", node_id)),
        score=attrs.get("score", ""),
        url=attrs.get("url", ""),
        size=attrs.get("size", 16),
        category=attrs.get("category", ""),
    )


def build_people_view(source: Graph) -> Graph:
    """Compress paper-centric graph into a people-centric relationship graph.

    Paper nodes are removed. Their titles are retained as edge evidence.
    """
    out = Graph()
    adjacency = defaultdict(list)
    for edge in source.edges.values():
        adjacency[edge["source"]].append(edge)
        adjacency[edge["target"]].append(edge)

    # Direction backbone.
    for node_id, attrs in source.nodes.items():
        if attrs.get("type") in {"direction", "track", "keyword"}:
            clone_node_for_people_view(out, node_id, attrs)
    for edge in source.edges.values():
        if edge["source"] in out.nodes and edge["target"] in out.nodes:
            out.add_edge(edge["source"], edge["target"], edge["relation"], weight=edge.get("weight", 1))

    # Schools / institutions, people, repos. Labs are converted into person-like PI/lab nodes.
    lab_to_people = defaultdict(list)
    for edge in source.edges.values():
        if edge["relation"] == "PI_OF":
            lab_to_people[edge["target"]].append(edge["source"])
            lab_to_people[edge["source"]].append(edge["target"])

    for node_id, attrs in source.nodes.items():
        typ = attrs.get("type")
        if typ in {"school", "institution"}:
            clone_node_for_people_view(out, node_id, attrs, "school")
        elif typ in {"person", "pi"}:
            clone_node_for_people_view(out, node_id, attrs, typ)
        elif typ == "lab":
            label = (attrs.get("label") or node_id).replace(" Lab", "")
            out.add_node(
                node_id,
                type="pi",
                label=label,
                title=attrs.get("title", label),
                score=attrs.get("score", ""),
                size=max(float(attrs.get("size", 18) or 18), 22),
            )
        elif typ == "repo":
            clone_node_for_people_view(out, node_id, attrs, "repo")

    # Keep non-paper structural edges that are useful in a person graph.
    for edge in source.edges.values():
        rel = edge["relation"]
        if rel in {"HAS_LAB", "PI_OF", "LINKED_REPO"}:
            if edge["source"] in out.nodes and edge["target"] in out.nodes:
                out.add_edge(edge["source"], edge["target"], rel, weight=edge.get("weight", 1))

    # Convert each paper into person-person, person-direction, person-school evidence.
    for paper_id, paper in source.nodes.items():
        if paper.get("type") != "paper":
            continue
        title = paper.get("title") or paper.get("label") or paper_id
        category = paper.get("category")
        track_node = f"track:{category}" if category else ""
        keyword_node = f"keyword:{category}" if category else ""

        people = []
        schools = []
        labs = []
        for edge in adjacency.get(paper_id, []):
            other = edge["target"] if edge["source"] == paper_id else edge["source"]
            other_type = source.nodes.get(other, {}).get("type")
            if other_type in {"person", "pi"}:
                people.append(other)
            elif other_type == "lab":
                labs.append(other)
                people.append(other)
            elif other_type in {"school", "institution"}:
                schools.append(other)

        # Excel-only papers carry authors as text rather than DB person ids.
        for idx, name in enumerate(split_authors(paper.get("authors", ""))[:10]):
            pn = person_node_id(name)
            out.add_node(
                pn,
                type="person",
                label=name,
                title=name,
                size=15 if idx == 0 else 10,
            )
            people.append(pn)

        # Remove duplicates while preserving order.
        people = list(dict.fromkeys(p for p in people if p in out.nodes))
        schools = list(dict.fromkeys(s for s in schools if s in out.nodes))

        if not people:
            continue

        # Direction connects to relevant people.
        for person in people[:12]:
            if track_node in out.nodes:
                out.add_edge(track_node, person, "MATCHES_DIRECTION", weight=2)
            if keyword_node in out.nodes:
                out.add_edge(keyword_node, person, "HAS_SIGNAL", weight=1)

        # School / institution connects mainly to first/lead people to avoid hairballs.
        for school in schools[:3]:
            for person in people[:3]:
                out.add_edge(school, person, "AFFILIATED_WITH", weight=1)

        # Lab/PI to authors.
        for lab in labs:
            for person in people[:8]:
                if lab != person:
                    add_aggregate_edge(out, lab, person, "RELATED_WORK", title, weight=2)

        # First author/star coauthor relation.
        lead = people[0]
        for person in people[1:10]:
            add_aggregate_edge(out, lead, person, "COAUTHOR", title, weight=1.5)

    # Convert aggregate edge evidence to readable hover titles.
    for edge in out.edges.values():
        ev = edge.get("evidence")
        if isinstance(ev, list) and ev:
            edge["title"] = f"{edge['relation']} · {edge.get('count', len(ev))} related paper(s): " + "; ".join(ev[:4])
        elif edge.get("count"):
            edge["title"] = f"{edge['relation']} · {edge.get('count')} related paper(s)"
    return out


def _match_lab_to_tracks(lab: sqlite3.Row, papers: list[sqlite3.Row], lab_score: float):
    stats = {
        track: {
            "score": 0.0,
            "paper_count": 0,
            "citations": 0,
            "evidence": [],
            "lab_keyword_hit": False,
        }
        for track in TRACKS
    }

    lab_text = " ".join(
        clean_cell(lab[key])
        for key in ("lab_name", "pi_name", "pi_name_cn", "keywords")
        if key in lab.keys()
    )
    _primary, lab_hits = classify(lab_text)
    for track in lab_hits:
        stats[track]["score"] += 6
        stats[track]["lab_keyword_hit"] = True

    for paper in papers:
        title_text = clean_cell(paper["title"])
        if skip_noisy_world_title(title_text):
            continue
        full_text = " ".join(
            clean_cell(paper[key])
            for key in ("title", "keywords_matched", "venue")
            if key in paper.keys()
        )
        _title_primary, title_hits = classify(title_text)
        _primary, hits = classify(full_text)
        for track in set(hits + title_hits):
            title_bonus = 4 if track in title_hits else 0
            citation_bonus = min(math.log1p(paper["citation_count"] or 0), 5)
            stats[track]["score"] += 2 + title_bonus + citation_bonus
            stats[track]["paper_count"] += 1
            stats[track]["citations"] += paper["citation_count"] or 0
            if title_text and title_text not in stats[track]["evidence"] and len(stats[track]["evidence"]) < 5:
                stats[track]["evidence"].append(title_text)

    matched = {}
    for track, item in stats.items():
        if item["score"] <= 0:
            continue
        item["score"] += min(float(lab_score or 0) / 20, 5)
        matched[track] = item
    return matched


def _add_person_node(graph: Graph, person_id: str, label: str, *, typ="person", title="", score=0, size=14):
    if person_id in graph.nodes:
        size = max(float(graph.nodes[person_id].get("size", 0) or 0), float(size or 0))
        if graph.nodes[person_id].get("type") == "pi" or typ == "pi":
            typ = "pi"
    graph.add_node(
        person_id,
        type=typ,
        label=label,
        title=title or label,
        score=score or "",
        size=size,
    )


def build_original_logic_graph(max_labs_per_track: int, max_students_per_lab: int) -> tuple[Graph, dict]:
    """Map the three World Model directions onto the original radar graph logic.

    Papers are used only for matching/evidence. The visual graph keeps direction,
    school, PI and high-confidence student nodes so the output stays readable.
    """
    graph = Graph()
    add_base_nodes(graph)

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    lab_scores = load_scores(con, "lab", "angel_radar_score")
    person_scores = load_scores(con, "person", "student_startup_score")
    lab_pi_names = {
        row["pi_name"]
        for row in con.execute("select pi_name from labs").fetchall()
        if row["pi_name"]
    }

    candidates = defaultdict(list)
    for lab in con.execute("select * from labs").fetchall():
        papers = con.execute("select * from papers where lab_id=?", (lab["id"],)).fetchall()
        matched = _match_lab_to_tracks(lab, papers, lab_scores.get(lab["id"], 0))
        for track, stats in matched.items():
            candidates[track].append((stats["score"], lab, stats))

    selected_counts = {}
    used_pi_nodes = set()
    for track, rows in candidates.items():
        rows.sort(key=lambda item: item[0], reverse=True)
        selected = rows[:max_labs_per_track]
        selected_counts[track] = {"matched_labs": len(rows), "shown_labs": len(selected)}

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

            evidence = "; ".join(stats["evidence"][:3])
            pi_title = f"{lab['school'] or ''} / {lab['lab_name'] or lab['pi_name']} Lab"
            if evidence:
                pi_title += f" | 方向证据: {evidence}"
            _add_person_node(
                graph,
                pi_node,
                lab["pi_name"],
                typ="pi",
                title=pi_title,
                score=pi_score,
                size=24 + min(float(score or 0), 20),
            )
            used_pi_nodes.add(pi_node)

            if lab["school"]:
                school_node = f"school:{lab['school']}"
                graph.add_node(school_node, type="school", label=lab["school"], size=24)
                graph.add_edge(school_node, pi_node, "AT_SCHOOL", weight=2)

            edge_title = (
                f"{TRACKS[track]['label']} · {stats['paper_count']} 条方向证据"
            )
            if evidence:
                edge_title += ": " + evidence
            graph.add_edge(
                f"track:{track}",
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
                  and r.confidence >= 0.5
                order by r.confidence desc
                limit ?
                """,
                (pi_id_for_edges, max_students_per_lab * 3),
            ).fetchall()
            added_students = 0
            for student in advisors:
                if student["is_pi"] or student["name"] in lab_pi_names:
                    continue
                if added_students >= max_students_per_lab:
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
                added_students += 1

    con.close()
    # PIs can be selected by multiple tracks; keep their largest visual size.
    for node_id in used_pi_nodes:
        node = graph.nodes[node_id]
        node["size"] = min(float(node.get("size", 24) or 24), 42)
    return graph, selected_counts


def write_json(graph: Graph, path: Path, meta):
    path.write_text(json.dumps(graph.as_dict(meta), ensure_ascii=False, indent=2), encoding="utf-8")


def graphml_value(value) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


def write_graphml(graph: Graph, path: Path):
    keys = ["label", "type", "title", "category", "year", "venue", "url", "source", "score", "size"]
    edge_keys = ["relation", "weight", "confidence"]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
    ]
    for key in keys:
        lines.append(f'<key id="{key}" for="node" attr.name="{key}" attr.type="string"/>')
    for key in edge_keys:
        lines.append(f'<key id="e_{key}" for="edge" attr.name="{key}" attr.type="string"/>')
    lines.append('<graph id="WorldModel" edgedefault="undirected">')
    for node in graph.nodes.values():
        lines.append(f'<node id="{html.escape(node["id"], quote=True)}">')
        for key in keys:
            if key in node:
                lines.append(f'<data key="{key}">{html.escape(graphml_value(node[key]))}</data>')
        lines.append("</node>")
    for idx, edge in enumerate(graph.edges.values()):
        lines.append(
            f'<edge id="e{idx}" source="{html.escape(edge["source"], quote=True)}" '
            f'target="{html.escape(edge["target"], quote=True)}">'
        )
        for key in edge_keys:
            if key in edge:
                lines.append(f'<data key="e_{key}">{html.escape(graphml_value(edge[key]))}</data>')
        lines.append("</edge>")
    lines.extend(["</graph>", "</graphml>"])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_html(graph: Graph, path: Path, meta):
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
        for key in ("title", "venue", "year", "score", "url"):
            if node.get(key):
                val = html.escape(str(node[key]))
                if key == "url":
                    val = f'<a href="{val}" target="_blank">{val}</a>'
                title_bits.append(f"{key}: {val}")
        node["title"] = "<br>".join(title_bits)
    for edge in data["edges"]:
        edge["from"] = edge.pop("source")
        edge["to"] = edge.pop("target")
        edge["title"] = edge.get("title") or edge.get("relation", "")
        edge["width"] = float(edge.get("weight", 1) or 1)
        relation = edge.get("relation")
        edge["length"] = {
            "ADVISES": 95,
            "AT_SCHOOL": 240,
            "MATCHES_DIRECTION": 220,
            "HAS_TRACK": 150,
        }.get(relation, 160)

    graph_json = json.dumps(data, ensure_ascii=False)
    legend = "".join(
        f'<div><span style="background:{DISPLAY_COLORS[key]}"></span>{label}</div>'
        for key, label in LEGEND_ITEMS
    )
    vis_path = ROOT / "lib" / "vis-9.1.2" / "vis-network.min.js"
    if vis_path.exists():
        vis_script = vis_path.read_text(encoding="utf-8").replace("</script>", "<\\/script>")
        vis_loader = f"<script>{vis_script}</script>"
    else:
        vis_loader = '<script src="../../lib/vis-9.1.2/vis-network.min.js"></script>'

    html_doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>World Model Direction Graph</title>
  <link rel="stylesheet" href="../../lib/vis-9.1.2/vis-network.css"/>
  {vis_loader}
  <style>
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    #graph {{ width:100vw; height:100vh; }}
    #panel {{
      position:fixed; left:16px; top:16px; z-index:10; width:330px;
      background:rgba(255,255,255,.94); border:1px solid #d1d5db; border-radius:8px;
      box-shadow:0 8px 30px rgba(15,23,42,.16); padding:12px 14px;
    }}
    h1 {{ font-size:18px; margin:0 0 6px; }}
    .meta {{ color:#475569; font-size:13px; line-height:1.45; }}
    .legend {{ display:grid; grid-template-columns:1fr 1fr; gap:5px 12px; margin-top:10px; font-size:13px; }}
    .legend span {{ display:inline-block; width:11px; height:11px; border-radius:50%; margin-right:6px; }}
    input {{ width:100%; box-sizing:border-box; margin-top:10px; padding:8px 9px; border:1px solid #cbd5e1; border-radius:6px; font-size:13px; }}
    button {{ margin-top:8px; padding:7px 9px; border:1px solid #cbd5e1; background:#f8fafc; border-radius:6px; cursor:pointer; font-size:13px; }}
    .filters {{ display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-top:10px; }}
    .filters button {{ margin:0; font-size:13px; }}
    .filters button.active {{ background:#111827; color:white; border-color:#111827; }}
  </style>
</head>
<body>
  <div id="panel">
    <h1>World Model Direction Graph</h1>
    <div class="meta">
      Nodes: {len(graph.nodes)} · Edges: {len(graph.edges)}<br/>
      Direction → PI → student relationships from radar data.
    </div>
    <div class="filters">
      <button id="filter-all" class="active" onclick="setFilter('all')">全部</button>
      <button id="filter-core" onclick="setFilter('core')">核心 World Model</button>
      <button id="filter-embodied" onclick="setFilter('embodied')">具身/机器人</button>
      <button id="filter-driving" onclick="setFilter('driving')">自动驾驶/4D</button>
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
    let activeCategory = 'all';
    const nodes = new vis.DataSet(data.nodes);
    const edges = new vis.DataSet(data.edges);
    const network = new vis.Network(document.getElementById('graph'), {{nodes, edges}}, {{
      physics: {{ stabilization: {{iterations: 220}}, barnesHut: {{ gravitationalConstant: -26000, springLength: 170 }} }},
      interaction: {{ hover: true, tooltipDelay: 80 }},
      nodes: {{ font: {{ size: 13, face: '-apple-system, Segoe UI, sans-serif', strokeWidth: 3 }} }},
      edges: {{ color: {{ color: '#94a3b8', highlight: '#334155' }}, smooth: {{ type: 'dynamic' }}, font: {{ size: 0 }} }}
    }});
    function fitGraph() {{ network.fit({{ animation: true }}); }}
    function visibleIdsFor(category) {{
      if (category === 'all') {{
        return new Set(originalNodes.map(n => n.id));
      }}
      const trackId = `track:${{category}}`;
      const ids = new Set(['direction:world_model', trackId]);
      const matchedPeople = new Set();
      for (const e of originalEdges) {{
        if (e.relation === 'MATCHES_DIRECTION' && e.from === trackId) {{
          ids.add(e.to);
          matchedPeople.add(e.to);
        }}
        if (e.relation === 'MATCHES_DIRECTION' && e.to === trackId) {{
          ids.add(e.from);
          matchedPeople.add(e.from);
        }}
      }}
      for (const e of originalEdges) {{
        const fromMatched = matchedPeople.has(e.from);
        const toMatched = matchedPeople.has(e.to);
        if (!fromMatched && !toMatched) continue;
        if (e.relation === 'ADVISES' || e.relation === 'AT_SCHOOL') {{
          ids.add(e.from);
          ids.add(e.to);
        }}
      }}
      return ids;
    }}
    function setFilter(category) {{
      activeCategory = category;
      for (const id of ['all', 'core', 'embodied', 'driving']) {{
        document.getElementById(`filter-${{id}}`).classList.toggle('active', id === category);
      }}
      applyFilters();
      setTimeout(fitGraph, 80);
    }}
    function applyFilters() {{
      const q = document.getElementById('search').value.toLowerCase().trim();
      const visible = visibleIdsFor(activeCategory);
      let keepIds = new Set();
      if (!q) {{
        keepIds = visible;
      }} else {{
        const matched = originalNodes.filter(n => {{
          if (!visible.has(n.id)) return false;
          const text = ((n.label || '') + ' ' + (n.title || '') + ' ' + (n.displayLabel || '')).toLowerCase();
          return text.includes(q);
        }}).map(n => n.id);
        keepIds = new Set(matched);
        let frontier = new Set(matched);
        for (let depth = 0; depth < 2; depth++) {{
          const next = new Set();
          for (const e of originalEdges) {{
            if (!visible.has(e.from) || !visible.has(e.to)) continue;
            const hitFrom = frontier.has(e.from);
            const hitTo = frontier.has(e.to);
            if (!hitFrom && !hitTo) continue;
            for (const id of [e.from, e.to]) {{
              if (!keepIds.has(id)) next.add(id);
              keepIds.add(id);
            }}
          }}
          frontier = next;
        }}
      }}
      const filteredNodes = originalNodes.filter(n => keepIds.has(n.id));
      const keep = new Set(filteredNodes.map(n => n.id));
      const filteredEdges = originalEdges.filter(e => keep.has(e.from) && keep.has(e.to));
      nodes.clear();
      edges.clear();
      nodes.add(filteredNodes);
      edges.add(filteredEdges);
    }}
    document.getElementById('search').addEventListener('input', applyFilters);
    window.setFilter = setFilter;
    window.fitGraph = fitGraph;
  </script>
</body>
</html>"""
    path.write_text(html_doc, encoding="utf-8")


def summarize(graph: Graph):
    counts = Counter(node.get("type", "?") for node in graph.nodes.values())
    tracks = defaultdict(int)
    for node in graph.nodes.values():
        if node.get("type") == "paper" and node.get("category"):
            tracks[node["category"]] += 1
    for edge in graph.edges.values():
        if edge.get("relation") == "MATCHES_DIRECTION" and edge.get("source", "").startswith("track:"):
            tracks[edge["source"].split(":", 1)[1]] += 1
    return {
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "node_types": dict(sorted(counts.items())),
        "track_nodes": dict(sorted(tracks.items())),
    }


def export_world_model_graph(
    *,
    max_labs_per_track: int = 10,
    max_students_per_lab: int = 6,
    out_dir: str | Path = EXPORTS_DIR,
):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    graph, track_counts = build_original_logic_graph(
        max_labs_per_track,
        max_students_per_lab,
    )

    meta = {
        "name": "World Model Direction Graph",
        "view": "original_direction_pi_student_school",
        "max_labs_per_track": max_labs_per_track,
        "max_students_per_lab": max_students_per_lab,
        "track_counts": track_counts,
        "db_path": str(DB_PATH),
    }
    meta.update(summarize(graph))

    write_json(graph, out_dir / "world_model_graph.json", meta)
    write_graphml(graph, out_dir / "world_model_graph.graphml")
    write_html(graph, out_dir / "world_model_graph.html", meta)
    return meta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-labs-per-track", type=int, default=10)
    parser.add_argument("--max-students-per-lab", type=int, default=6)
    parser.add_argument("--out-dir", default=str(EXPORTS_DIR))
    args = parser.parse_args()

    meta = export_world_model_graph(
        max_labs_per_track=args.max_labs_per_track,
        max_students_per_lab=args.max_students_per_lab,
        out_dir=args.out_dir,
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
