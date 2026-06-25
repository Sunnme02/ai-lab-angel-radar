"""定制子图查询:按老师(ego)/方向/学校 各出一张聚焦小图(替代毛球全图)。

复用 export_graph 的节点着色与边样式约定(type / size / confidence)。
"""
import networkx as nx

from ..models import Lab, Paper, Person, PersonRepoLink, Relationship, Repo, Score


def _scores(sess, etype, sname):
    return {s.entity_id: s.score_value for s in
            sess.query(Score).filter(Score.entity_type == etype,
                                     Score.score_name == sname).all()}


def _add_lab(G, sess, lab, ls, ps, max_students=25, with_students=True):
    """把一个 lab 的子树加入图:school→lab→PI→(ADVISES)学生→repo + 关键词。"""
    ln = f"lab:{lab.id}"
    G.add_node(ln, type="lab", label=f"{lab.pi_name} Lab",
               size=18 + ls.get(lab.id, 0) / 5, score=ls.get(lab.id, 0))
    if lab.school:
        sn = f"school:{lab.school}"
        if sn not in G:
            G.add_node(sn, type="school", label=lab.school, size=26)
        G.add_edge(sn, ln, relation="HAS_LAB")
    for kw in (lab.keywords or "").split(","):
        kw = kw.strip()
        if kw:
            kn = f"keyword:{kw.lower()}"
            if kn not in G:
                G.add_node(kn, type="keyword", label=kw, size=11)
            G.add_edge(ln, kn, relation="MATCHES_KEYWORD")

    pi = sess.query(Person).filter(Person.is_pi == True,  # noqa: E712
                                   Person.name == lab.pi_name).first()
    pin = None
    if pi:
        pin = f"person:{pi.id}"
        G.add_node(pin, type="pi", label=pi.name, size=22, score=ps.get(pi.id, 0))
        G.add_edge(pin, ln, relation="PI_OF")
        if with_students:
            advs = (sess.query(Relationship).filter(
                Relationship.relation_type == "ADVISES", Relationship.source_id == pi.id,
                Relationship.confidence >= 0.5)
                .order_by(Relationship.confidence.desc()).limit(max_students).all())
            for r in advs:
                stu = sess.get(Person, r.target_id)
                if not stu:
                    continue
                sid = f"person:{stu.id}"
                G.add_node(sid, type="person", label=stu.name,
                           size=8 + ps.get(stu.id, 0) / 8, score=ps.get(stu.id, 0))
                G.add_edge(pin, sid, relation="ADVISES", confidence=r.confidence,
                           weight=r.confidence)
                for lk in sess.query(PersonRepoLink).filter(
                        PersonRepoLink.person_id == stu.id).all():
                    repo = sess.get(Repo, lk.repo_id)
                    if repo:
                        rn = f"repo:{repo.id}"
                        if rn not in G:
                            G.add_node(rn, type="repo", label=f"{repo.repo_name}★{repo.stars}",
                                       size=8 + min((repo.stars or 0) ** 0.5 / 3, 24),
                                       score=repo.stars)
                        G.add_edge(sid, rn, relation="MAINTAINS", confidence=lk.confidence)
    return ln, pin


def ego_pi(sess, pi_name, max_students=30):
    """以某老师为"恒星"的 ego 图。"""
    G = nx.Graph()
    ls, ps = _scores(sess, "lab", "angel_radar_score"), _scores(sess, "person", "student_startup_score")
    lab = sess.query(Lab).filter(Lab.pi_name == pi_name).first()
    if not lab:
        return G
    _ln, pin = _add_lab(G, sess, lab, ls, ps, max_students=max_students, with_students=True)
    if pin and pin in G:
        G.nodes[pin]["size"] = 36          # 恒星放大
        G.nodes[pin]["color_hint"] = "star"
    return G


def by_direction(sess, direction, max_labs=15):
    """按方向出图:命中该方向的实验室(按分排序)+ 各自 PI/学生,围绕一个方向中心节点。"""
    G = nx.Graph()
    ls, ps = _scores(sess, "lab", "angel_radar_score"), _scores(sess, "person", "student_startup_score")
    dl = direction.lower()
    matched = []
    for lab in sess.query(Lab).all():
        kws = (lab.keywords or "").lower()
        pdir = " ".join((p.keywords_matched or "") for p in
                        sess.query(Paper).filter(Paper.lab_id == lab.id).all()).lower()
        if dl in kws or dl in pdir:
            matched.append(lab)
    matched.sort(key=lambda l: ls.get(l.id, 0), reverse=True)
    kn = f"keyword:{dl}"
    G.add_node(kn, type="keyword", label=direction, size=32)
    for lab in matched[:max_labs]:
        ln, _pin = _add_lab(G, sess, lab, ls, ps, max_students=6, with_students=True)
        G.add_edge(ln, kn, relation="MATCHES_KEYWORD")
    return G, len(matched)


def by_school(sess, school, max_students=6):
    """某学校的师承子图。"""
    G = nx.Graph()
    ls, ps = _scores(sess, "lab", "angel_radar_score"), _scores(sess, "person", "student_startup_score")
    for lab in sess.query(Lab).filter(Lab.school == school).all():
        _add_lab(G, sess, lab, ls, ps, max_students=max_students, with_students=True)
    return G


def all_directions(sess):
    """数据里出现过的方向标签(供下拉)。"""
    tags = set()
    for lab in sess.query(Lab).all():
        for k in (lab.keywords or "").split(","):
            if k.strip():
                tags.add(k.strip())
    for p in sess.query(Paper).all():
        for k in (p.keywords_matched or "").split(","):
            if k.strip():
                tags.add(k.strip())
    return sorted(tags)
