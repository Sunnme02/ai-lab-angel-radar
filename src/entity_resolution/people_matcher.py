"""人物消歧/合并(规格 8.6)。保留 raw_name 和 normalized_name,匹配带 confidence。"""
import re

from rapidfuzz import fuzz

from ..models import Person
from ..utils.text import normalize_name

# 机构通用词(比较时剔除,避免"X University"与"Y University"因 University 误判相同)
_GENERIC = re.compile(r"\b(university|univ|institute|college|school|of|the|laboratory|"
                      r"lab|department|dept|tech|technology)\b", re.I)


def _aff_core(a: str) -> str:
    return _GENERIC.sub(" ", a or "").strip().lower()


def find_or_create_person(db, sess, name, openalex_author_id=None,
                          affiliation=None, name_cn=None):
    """按规则找已有人或新建。返回 Person。

    规则:
    - OpenAlex author id 一致 → 同一人(最强)
    - 规范化姓名一致 + (机构相近 或 无机构信息) → 同一人
    - 同名但机构明显不同 → 不合并(新建)
    """
    norm = normalize_name(name)
    if not norm:
        return None

    # 1) OpenAlex id 精确
    if openalex_author_id:
        obj = sess.query(Person).filter(
            Person.openalex_author_id == openalex_author_id).first()
        if obj:
            _enrich(obj, name, affiliation, name_cn)
            sess.flush()
            return obj

    # 2) 规范化姓名候选
    candidates = sess.query(Person).filter(Person.normalized_name == norm).all()
    for c in candidates:
        if c.openalex_author_id and openalex_author_id and c.openalex_author_id != openalex_author_id:
            continue  # 不同 OpenAlex id → 不是同一人
        if affiliation and c.affiliation:
            core_a, core_c = _aff_core(affiliation), _aff_core(c.affiliation)
            if core_a and core_c and fuzz.token_sort_ratio(core_a, core_c) < 60:
                continue  # 机构特征词明显不同 → 不合并
        _enrich(c, name, affiliation, name_cn, openalex_author_id)
        sess.flush()
        return c

    # 3) 新建
    obj = Person(name=name, raw_name=name, normalized_name=norm,
                 affiliation=affiliation, name_cn=name_cn,
                 openalex_author_id=openalex_author_id)
    sess.add(obj)
    sess.flush()
    return obj


def _enrich(obj, name, affiliation, name_cn, openalex_author_id=None):
    if affiliation and not obj.affiliation:
        obj.affiliation = affiliation
    if name_cn and not obj.name_cn:
        obj.name_cn = name_cn
    if openalex_author_id and not obj.openalex_author_id:
        obj.openalex_author_id = openalex_author_id


# ---------------- 合并 pass:并掉被拆开的同一人节点 ----------------
def merge_duplicate_people(db, sess):
    """合并同名且高度疑似同一人的 Person 节点(OpenAlex 把同一人拆成多档时)。

    合并条件(保守,避免误并不同人):同名 + 机构相容(不冲突) +
    (共享实验室 或 共同作者重合)。返回合并掉的节点数。
    """
    from collections import defaultdict

    from ..models import Authorship, Paper, Person, PersonRepoLink, Relationship

    paper_authors, person_papers = defaultdict(set), defaultdict(set)
    for a in sess.query(Authorship).all():
        paper_authors[a.paper_id].add(a.person_id)
        person_papers[a.person_id].add(a.paper_id)
    person_labs = defaultdict(set)
    for p in sess.query(Paper).all():
        if p.lab_id:
            for pid in paper_authors.get(p.id, ()):
                person_labs[pid].add(p.lab_id)

    def coauthors(pid):
        s = set()
        for pp in person_papers[pid]:
            s |= paper_authors[pp]
        s.discard(pid)
        return s

    def compatible_aff(a, b):
        ca, cb = _aff_core(a.affiliation or ""), _aff_core(b.affiliation or "")
        if ca and cb:
            return fuzz.token_sort_ratio(ca, cb) >= 60
        return True  # 一方机构缺失 → 视为相容

    def same_person(a, b):
        if not compatible_aff(a, b):
            return False
        if person_labs[a.id] & person_labs[b.id]:
            return True
        return bool(coauthors(a.id) & coauthors(b.id))

    groups = defaultdict(list)
    for p in sess.query(Person).all():
        if p.normalized_name:
            groups[p.normalized_name].append(p)

    merged = 0
    for _name, recs in groups.items():
        if len(recs) < 2:
            continue
        used = set()
        for i, ri in enumerate(recs):
            if ri.id in used:
                continue
            cluster = [ri]
            for rj in recs[i + 1:]:
                if rj.id in used:
                    continue
                if any(same_person(c, rj) for c in cluster):
                    cluster.append(rj)
                    used.add(rj.id)
            if len(cluster) > 1:
                merged += _merge_cluster(sess, cluster, Authorship, PersonRepoLink, Relationship)
    sess.commit()
    return merged


def _merge_cluster(sess, cluster, Authorship, PersonRepoLink, Relationship):
    def rank(p):  # 选信息最全的做规范节点
        return (1 if p.openalex_author_id else 0, 1 if p.affiliation else 0,
                1 if p.is_pi else 0, len(p.name or ""))
    canon = max(cluster, key=rank)
    n = 0
    for d in [p for p in cluster if p.id != canon.id]:
        for f in ["affiliation", "name_cn", "homepage_url", "github_url",
                  "google_scholar_url", "semantic_scholar_author_id", "openalex_author_id"]:
            if not getattr(canon, f) and getattr(d, f):
                setattr(canon, f, getattr(d, f))
        canon.is_pi = canon.is_pi or d.is_pi
        canon.is_student_candidate = canon.is_student_candidate or d.is_student_candidate
        if canon.role in (None, "Unknown") and d.role not in (None, "Unknown"):
            canon.role = d.role

        for a in sess.query(Authorship).filter(Authorship.person_id == d.id).all():
            ex = sess.query(Authorship).filter(Authorship.person_id == canon.id,
                                               Authorship.paper_id == a.paper_id).first()
            sess.delete(a) if ex else setattr(a, "person_id", canon.id)
        for lk in sess.query(PersonRepoLink).filter(PersonRepoLink.person_id == d.id).all():
            ex = sess.query(PersonRepoLink).filter(PersonRepoLink.person_id == canon.id,
                                                   PersonRepoLink.repo_id == lk.repo_id).first()
            sess.delete(lk) if ex else setattr(lk, "person_id", canon.id)
        for r in sess.query(Relationship).filter(Relationship.source_type == "person",
                                                 Relationship.source_id == d.id).all():
            ex = sess.query(Relationship).filter(
                Relationship.source_type == "person", Relationship.source_id == canon.id,
                Relationship.target_type == r.target_type, Relationship.target_id == r.target_id,
                Relationship.relation_type == r.relation_type).first()
            sess.delete(r) if ex else setattr(r, "source_id", canon.id)
        for r in sess.query(Relationship).filter(Relationship.target_type == "person",
                                                 Relationship.target_id == d.id).all():
            ex = sess.query(Relationship).filter(
                Relationship.target_type == "person", Relationship.target_id == canon.id,
                Relationship.source_type == r.source_type, Relationship.source_id == r.source_id,
                Relationship.relation_type == r.relation_type).first()
            sess.delete(r) if ex else setattr(r, "target_id", canon.id)
        sess.flush()
        sess.delete(d)
        n += 1
    sess.flush()
    return n
