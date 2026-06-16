"""从数据库构建 NetworkX 图(规格 8.9)。

build_graph: 完整图(含论文/全部作者),用于中心性计算。
build_core_graph: 精简核心图(只留 lab/PI/高潜学生/repo/keyword),用于可视化,避免毛球。
"""
import json

import networkx as nx

from ..models import (Authorship, Lab, Paper, Person, PersonRepoLink, Relationship,
                      Repo, Score)


def build_graph(sess):
    G = nx.Graph()

    labs = {l.id: l for l in sess.query(Lab).all()}
    people = {p.id: p for p in sess.query(Person).all()}
    papers = {p.id: p for p in sess.query(Paper).all()}
    repos = {r.id: r for r in sess.query(Repo).all()}

    schools = set()
    for l in labs.values():
        lab_node = f"lab:{l.id}"
        G.add_node(lab_node, type="lab", label=f"{l.pi_name} Lab", school=l.school,
                   pi=l.pi_name)
        if l.school:
            sn = f"school:{l.school}"
            if l.school not in schools:
                G.add_node(sn, type="school", label=l.school)
                schools.add(l.school)
            G.add_edge(sn, lab_node, relation="HAS_LAB")
        # 关键词节点
        for kw in (l.keywords or "").split(","):
            kw = kw.strip()
            if kw:
                kn = f"keyword:{kw.lower()}"
                G.add_node(kn, type="keyword", label=kw)
                G.add_edge(lab_node, kn, relation="MATCHES_KEYWORD")

    for p in papers.values():
        pn = f"paper:{p.id}"
        G.add_node(pn, type="paper", label=(p.title or "")[:50], year=p.year,
                   citations=p.citation_count)
        if p.lab_id and p.lab_id in labs:
            G.add_edge(f"lab:{p.lab_id}", pn, relation="LAB_PAPER")

    for person in people.values():
        nn = f"person:{person.id}"
        G.add_node(nn, type="person", label=person.name, role=person.role,
                   is_pi=person.is_pi, is_student=person.is_student_candidate)
        if person.is_pi:
            # PI 连到其 lab(按姓名匹配)
            for l in labs.values():
                if l.pi_name == person.name:
                    G.add_edge(nn, f"lab:{l.id}", relation="PI_OF")

    for a in sess.query(Authorship).all():
        nn, pn = f"person:{a.person_id}", f"paper:{a.paper_id}"
        if nn in G and pn in G:
            G.add_edge(nn, pn, relation="FIRST_AUTHOR_OF" if a.is_first_author else "AUTHOR_OF")
            # 学生 → lab(经论文)
            pap = papers.get(a.paper_id)
            if pap and pap.lab_id:
                G.add_edge(nn, f"lab:{pap.lab_id}", relation="MEMBER_OF")

    for r in repos.values():
        rn = f"repo:{r.id}"
        G.add_node(rn, type="repo", label=r.repo_name, stars=r.stars)
    for link in sess.query(PersonRepoLink).all():
        nn, rn = f"person:{link.person_id}", f"repo:{link.repo_id}"
        if nn in G and rn in G:
            rel = "MAINTAINS" if link.link_type in ("owner", "homepage_link") else "CONTRIBUTES_TO"
            G.add_edge(nn, rn, relation=rel, confidence=link.confidence)

    return G


def build_core_graph(sess):
    """精简核心图(可视化用):school / lab / PI / 高潜学生 / repo / keyword。

    只保留对投资雷达有意义的节点,论文与路人共同作者不画。节点大小反映分数。
    """
    G = nx.Graph()
    lab_scores = {s.entity_id: s.score_value for s in
                  sess.query(Score).filter(Score.entity_type == "lab",
                                           Score.score_name == "angel_radar_score").all()}
    person_scores = {s.entity_id: s.score_value for s in
                     sess.query(Score).filter(Score.entity_type == "person",
                                              Score.score_name == "student_startup_score").all()}

    labs = {l.id: l for l in sess.query(Lab).all()}
    schools = set()
    for l in labs.values():
        ln = f"lab:{l.id}"
        G.add_node(ln, type="lab", label=f"{l.pi_name} Lab", score=lab_scores.get(l.id, 0),
                   size=20 + lab_scores.get(l.id, 0) / 4)
        if l.school:
            sn = f"school:{l.school}"
            if l.school not in schools:
                G.add_node(sn, type="school", label=l.school, size=26)
                schools.add(l.school)
            G.add_edge(sn, ln, relation="HAS_LAB")
        for kw in (l.keywords or "").split(","):
            kw = kw.strip()
            if kw:
                kn = f"keyword:{kw.lower()}"
                if kn not in G:
                    G.add_node(kn, type="keyword", label=kw, size=12)
                G.add_edge(ln, kn, relation="MATCHES_KEYWORD")

    # 学生候选:只保留"有 repo 或 一作≥2"的高潜学生 + 所有 PI
    repo_links = sess.query(PersonRepoLink).all()
    people_with_repo = {l.person_id for l in repo_links}
    keep_people = set()
    for p in sess.query(Person).all():
        if p.is_pi:
            keep_people.add(p.id)
            continue
        if not p.is_student_candidate:
            continue
        fa = sess.query(Authorship).filter(Authorship.person_id == p.id,
                                           Authorship.is_first_author == True).count()  # noqa: E712
        if p.id in people_with_repo or fa >= 2:
            keep_people.add(p.id)

    for pid in keep_people:
        p = sess.get(Person, pid)
        nn = f"person:{pid}"
        sc = person_scores.get(pid, 0)
        G.add_node(nn, type="pi" if p.is_pi else "person", label=p.name,
                   score=sc, size=(24 if p.is_pi else 10 + sc / 6))
        # PI → lab
        if p.is_pi:
            for l in labs.values():
                if l.pi_name == p.name:
                    G.add_edge(nn, f"lab:{l.id}", relation="PI_OF")

    # 导师 → 学生(ADVISES 置信度边,粗细=置信度;替代一刀切的 MEMBER_OF)
    for rel in sess.query(Relationship).filter(Relationship.relation_type == "ADVISES").all():
        sn, tn = f"person:{rel.source_id}", f"person:{rel.target_id}"
        if sn in G and tn in G:
            G.add_edge(sn, tn, relation="ADVISES", confidence=rel.confidence,
                       weight=rel.confidence)

    # repo 节点 + 人→repo
    for link in repo_links:
        if link.person_id not in keep_people:
            continue
        r = sess.get(Repo, link.repo_id)
        if not r:
            continue
        rn = f"repo:{r.id}"
        if rn not in G:
            G.add_node(rn, type="repo", label=f"{r.repo_name}★{r.stars}",
                       score=r.stars, size=10 + min((r.stars or 0) ** 0.5 / 3, 30))
        rel = "MAINTAINS" if link.link_type in ("owner", "homepage_link") else "CONTRIBUTES_TO"
        G.add_edge(f"person:{link.person_id}", rn, relation=rel, confidence=link.confidence)

    return G
