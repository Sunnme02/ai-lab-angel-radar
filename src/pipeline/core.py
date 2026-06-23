"""Pipeline 编排(规格第9节):采集→消歧→分类→关系→评分→图谱→导出。"""
import re
from collections import defaultdict

from rapidfuzz import fuzz

from ..classifiers.keyword_classifier import classify_text, match_focus_keywords
from ..classifiers.startup_signal_classifier import detect_signals
from ..collectors.academic.openalex import OpenAlexCollector
from ..collectors.academic.semantic_scholar import SemanticScholarCollector
from ..collectors.github.github_api import GitHubCollector, logins_from_links
from ..collectors.web.homepage import fetch_homepage
from ..config import Config
from ..db import DB
from ..entity_resolution.paper_matcher import find_or_create_paper
from ..entity_resolution.people_matcher import find_or_create_person, merge_duplicate_people
from ..export import export_all
from ..graph.build_graph import build_graph
from ..graph.network_metrics import compute_centrality
from ..models import (Authorship, Lab, Paper, Person, PersonRepoLink, Relationship, Repo, Score)
from ..scoring.lab_score import score_lab
from ..scoring.person_score import score_person
from ..scoring.repo_score import score_repo
from ..scoring.score_utils import contact_priority, priority
from ..utils.logging import get_logger

log = get_logger()

COMPANY_AFF = re.compile(r"\b(inc|ltd|corp|company|technolog|huawei|tencent|alibaba|baidu|"
                         r"bytedance|microsoft|google|meta|nvidia|amazon|sensetime|megvii)\b|"
                         r"公司|华为|腾讯|阿里|字节|百度|商汤", re.I)


class Context:
    def __init__(self, config: Config):
        self.cfg = config
        self.db = DB(config.db_path)
        self.oa = OpenAlexCollector(email=config.openalex_email,
                                    cache_dir=config.openalex_cache_dir)
        self.s2 = SemanticScholarCollector(api_key=config.s2_key)
        self.gh = GitHubCollector(token=config.github_token)


def _add_rel(db, sess, st, sid, tt, tid, rel, conf=1.0, ev_text="", ev_url=""):
    db.upsert(sess, Relationship,
              {"source_type": st, "source_id": sid, "target_type": tt,
               "target_id": tid, "relation_type": rel},
              {"confidence": conf, "evidence_text": ev_text[:400], "evidence_url": ev_url})


def process_lab(ctx: Context, school: str, lab_seed: dict):
    cfg, db = ctx.cfg, ctx.db
    pi_name = lab_seed["pi_name"]
    focus = list(cfg.keywords) + list(lab_seed.get("keywords", []))
    log.info(f"=== 处理 {school} / {pi_name} ===")

    with db.session() as sess:
        lab = db.upsert(sess, Lab, {"school": school, "pi_name": pi_name},
                        {"pi_name_cn": lab_seed.get("pi_name_cn"),
                         "homepage_url": lab_seed.get("homepage_url"),
                         "keywords": ",".join(lab_seed.get("keywords", [])),
                         "lab_name": f"{pi_name} Lab"})
        lab_id = lab.id
        sess.commit()

    # 2.1 取论文(有 ORCID 则精确锚定作者,避免常见名串人)
    author_id, papers = ctx.oa.collect_lab(pi_name, school, cfg.year_from, cfg.year_to,
                                            cfg.max_papers_per_lab, orcid=lab_seed.get("orcid"))

    with db.session() as sess:
        lab = sess.get(Lab, lab_id)
        # PI 人物
        pi = find_or_create_person(db, sess, pi_name, openalex_author_id=author_id,
                                   affiliation=school, name_cn=lab_seed.get("pi_name_cn"))
        pi.is_pi = True
        pi.role = "PI"
        pi.homepage_url = pi.homepage_url or lab_seed.get("homepage_url")
        pi.google_scholar_url = pi.google_scholar_url or lab_seed.get("scholar_url")
        sess.flush()
        _add_rel(db, sess, "person", pi.id, "lab", lab_id, "PI_OF_LAB")

        # 2.2-2.3 论文 + 作者 + 一作/学生候选
        for p in papers:
            tags = classify_text((p.get("title") or "") + " " + (p.get("abstract") or ""))
            mk = match_focus_keywords((p.get("title") or "") + " " + (p.get("abstract") or ""), focus)
            p["keywords_matched"] = sorted(set(tags) | set(mk))
            paper = find_or_create_paper(db, sess, lab_id, p)
            if not paper:
                continue
            for a in p.get("authors", []):
                inst0 = (a.get("institutions") or [{}])[0].get("name")
                person = find_or_create_person(db, sess, a["name"],
                                               openalex_author_id=a.get("openalex_author_id"),
                                               affiliation=inst0)
                if not person:
                    continue
                is_first = a.get("author_position") == "first"
                db.upsert(sess, Authorship,
                          {"paper_id": paper.id, "person_id": person.id},
                          {"author_order": a.get("order"), "is_first_author": is_first,
                           "is_corresponding_author": a.get("is_corresponding", False),
                           "affiliation_at_publication": inst0})
                _add_rel(db, sess, "person", person.id, "paper", paper.id,
                         "FIRST_AUTHOR_OF" if is_first else "AUTHOR_OF")
                # 企业 affiliation → 产业连接信号
                if inst0 and COMPANY_AFF.search(inst0):
                    _add_rel(db, sess, "lab", lab_id, "company", 0,
                             "COLLABORATES_WITH_COMPANY", 0.6,
                             f"co-author affiliation: {inst0}", paper.url or "")
        sess.commit()

    # 2.3b 师生关系置信度(合作频次 + 同机构 + 一作)→ ADVISES 边 + is_student_candidate
    _compute_advisor_links(ctx, lab_id, pi_name, school)

    # 2.4 主页(实验室/PI 主页:成员信号 + GitHub 链接 + 创业信号)
    hp_url = lab_seed.get("homepage_url")
    if hp_url:
        hp = fetch_homepage(hp_url)
        if hp:
            with db.session() as sess:
                for sig in detect_signals(hp["text"], hp_url):
                    _add_rel(db, sess, "lab", lab_id, "lab", lab_id,
                             "POTENTIAL_STARTUP_SIGNAL", sig["confidence"],
                             f"{sig['signal_type']}: {sig['evidence_text']}", hp_url)
                sess.commit()

    # 2.5-2.8 GitHub(需 token)
    if ctx.gh.enabled:
        _collect_github(ctx, lab_id, pi_name, focus, lab_seed.get("homepage_url"))
    else:
        log.warning("无 GITHUB_TOKEN → 跳过 GitHub 采集(工程信号将偏低)")


def _compute_advisor_links(ctx, lab_id, pi_name, school):
    """从共同作者推断"导师→学生"置信度(不丢合作信息,只是不再硬贴学生标签)。

    confidence = f(与PI合作论文数 joint, 是否同机构 same_inst, 是否当过一作 has_fa)。
    写入 ADVISES 关系(PI→人,带 confidence);is_student_candidate = confidence>=0.5。
    """
    db = ctx.db
    with db.session() as sess:
        lab_paper_ids = [p.id for p in sess.query(Paper).filter(Paper.lab_id == lab_id).all()]
        pi = sess.query(Person).filter(Person.is_pi == True,  # noqa: E712
                                       Person.name == pi_name).first()
        if not pi or not lab_paper_ids:
            return
        joint, has_fa = defaultdict(int), defaultdict(bool)
        for a in sess.query(Authorship).filter(Authorship.paper_id.in_(lab_paper_ids)).all():
            joint[a.person_id] += 1
            if a.is_first_author:
                has_fa[a.person_id] = True
        school_l = school.lower()
        for pid, jc in joint.items():
            if pid == pi.id:
                continue
            person = sess.get(Person, pid)
            aff = (person.affiliation or "").strip()
            same = bool(aff and fuzz.partial_ratio(school_l, aff.lower()) >= 75)
            diff = bool(aff and not same)        # 明确填了别的机构 = 外校合作者
            if same:                              # 同校:最可能是其学生
                conf = 0.85 if jc >= 3 else 0.7 if jc >= 2 else 0.55
            elif not aff:                         # 机构缺失:很多真学生如此,按合作频次给
                conf = 0.6 if jc >= 3 else 0.5 if jc >= 2 else 0.35
            else:                                 # 外校:即使高频也只算"疑似合作者"
                conf = 0.45 if jc >= 3 else 0.3 if jc >= 2 else 0.2
            if has_fa[pid]:
                conf = min(0.95, conf + 0.1)
            if diff:                              # 外校硬上限,不让一作 boost 顶过学生阈值
                conf = min(conf, 0.45)
            conf = round(conf, 2)
            person.is_student_candidate = conf >= 0.5
            if person.is_student_candidate and person.role == "Unknown":
                person.role = "PhD"
            _add_rel(db, sess, "person", pi.id, "person", pid, "ADVISES", conf,
                     f"合作{jc}篇 同机构={same} 当过一作={has_fa[pid]}")
        sess.commit()


def _resolve_github_login(ctx, name, homepage, hints):
    """返回 (login, confidence, link_type)。主页直链优先,否则搜用户核名。"""
    if homepage:
        hp = fetch_homepage(homepage)
        if hp:
            for lg in logins_from_links(hp.get("github_links", [])):
                return lg, 0.95, "homepage_link"
    lg, conf = ctx.gh.find_user(name, hints)
    if lg and conf >= 0.55:
        return lg, conf, "owner"
    return None, 0.0, None


def _collect_github(ctx, lab_id, pi_name, focus, pi_homepage=None):
    cfg, db = ctx.cfg, ctx.db
    with db.session() as sess:
        students = sess.query(Person).join(
            Authorship, Authorship.person_id == Person.id).join(
            Paper, Paper.id == Authorship.paper_id).filter(
            Paper.lab_id == lab_id, Person.is_student_candidate == True).distinct().all()  # noqa: E712
        targets = [(sess.get(Person, p.id).name, p.id, p.homepage_url) for p in students[:8]]
        pi = sess.query(Person).filter(Person.is_pi == True,  # noqa: E712
                                       Person.name == pi_name).first()
        if pi:
            targets.insert(0, (pi.name, pi.id, pi.homepage_url or pi_homepage))

    hints = ",".join(list(focus)[:6])
    for name, pid, homepage in targets:
        login, conf, link_type = _resolve_github_login(ctx, name, homepage, hints)
        if not login:
            continue
        repos = ctx.gh.list_user_repos(login, focus, limit=cfg.max_repos_per_author)
        for r in repos:
            r["readme_text"] = ctx.gh.get_readme(r["owner"], r["repo_name"])
            mk = match_focus_keywords((r.get("description") or "") + " " +
                                      (r.get("readme_text") or "") + " " + (r.get("topics") or ""), focus)
            with db.session() as sess:
                repo = db.upsert(sess, Repo, {"url": r["url"]},
                                 {k: r.get(k) for k in
                                  ["repo_name", "owner", "description", "readme_text", "stars",
                                   "forks", "watchers", "open_issues", "topics", "language"]})
                repo.matched_keywords = ",".join(mk)
                sess.flush()
                db.upsert(sess, PersonRepoLink, {"person_id": pid, "repo_id": repo.id},
                          {"link_type": link_type, "confidence": conf})
                _add_rel(db, sess, "person", pid, "repo", repo.id,
                         "MAINTAINS_REPO" if link_type in ("owner", "homepage_link")
                         else "CONTRIBUTES_TO_REPO", conf)
                for sig in detect_signals((r.get("readme_text") or "") + " " + (r.get("description") or ""),
                                          r["url"]):
                    _add_rel(db, sess, "repo", repo.id, "repo", repo.id,
                             "POTENTIAL_STARTUP_SIGNAL", sig["confidence"],
                             f"{sig['signal_type']}: {sig['evidence_text']}", r["url"])
                sess.commit()


# ---------------- finalize:图谱中心性 → 评分 → 导出 ----------------
def finalize(ctx: Context):
    db = ctx.db
    with db.session() as sess:
        merged = merge_duplicate_people(db, sess)
        # 清理被合并/删除实体的孤儿分数
        pid_set = {p.id for p in sess.query(Person.id).all()}
        for s in sess.query(Score).filter(Score.entity_type == "person").all():
            if s.entity_id not in pid_set:
                sess.delete(s)
        sess.commit()
        log.info(f"实体消歧:合并重复人物节点 {merged} 个")
    with db.session() as sess:
        G = build_graph(sess)
        cen = compute_centrality(G)

        # 学生评分
        people = sess.query(Person).all()
        for person in people:
            stats = _person_stats(sess, person, cen.get(person.id, {}).get("centrality", 0))
            res = score_person(stats)
            db.save_score(sess, "person", person.id, "student_startup_score",
                          res["total_score"], {**res, "contact_priority": contact_priority(res["total_score"])})

        # repo 评分
        for repo in sess.query(Repo).all():
            res = score_repo(_repo_stats(sess, repo))
            db.save_score(sess, "repo", repo.id, "productization_score", res["total_score"], res)

        # 实验室评分
        for lab in sess.query(Lab).all():
            res = score_lab(_lab_stats(sess, lab))
            db.save_score(sess, "lab", lab.id, "angel_radar_score",
                          res["total_score"], {**res, "priority": priority(res["total_score"])})
        sess.commit()

        return export_all(db, sess, ctx.cfg.exports_dir)


def _person_stats(sess, person, centrality):
    auths = sess.query(Authorship).filter(Authorship.person_id == person.id).all()
    fa = sum(1 for a in auths if a.is_first_author)
    related = len(auths)
    links = sess.query(PersonRepoLink).filter(PersonRepoLink.person_id == person.id).all()
    repo_ids = [l.repo_id for l in links]
    repos = sess.query(Repo).filter(Repo.id.in_(repo_ids)).all() if repo_ids else []
    max_stars = max([r.stars or 0 for r in repos], default=0)
    mk = set()
    for r in repos:
        mk |= set((r.matched_keywords or "").split(","))
    mk.discard("")
    prod = sess.query(Relationship).filter(
        Relationship.source_type == "repo", Relationship.source_id.in_(repo_ids or [-1]),
        Relationship.relation_type == "POTENTIAL_STARTUP_SIGNAL").count() if repo_ids else 0
    return {
        "first_author_count_3y": fa, "related_paper_count": related,
        "max_repo_stars": max_stars, "repo_count": len(repos),
        "repo_active": any(r.stars for r in repos),
        "matched_keyword_count": len(mk), "productization_signal_count": prod,
        "industry_signal_count": 0, "centrality": centrality, "role": person.role,
    }


def _repo_stats(sess, repo):
    sigs = sess.query(Relationship).filter(
        Relationship.source_type == "repo", Relationship.source_id == repo.id,
        Relationship.relation_type == "POTENTIAL_STARTUP_SIGNAL").count()
    mk = [x for x in (repo.matched_keywords or "").split(",") if x]
    vertical = any(k in ("Recommendation", "Embodied AI", "AI for Finance",
                         "AI for Healthcare") for k in mk)
    return {"stars": repo.stars, "forks": repo.forks, "open_issues": repo.open_issues,
            "last_commit_at": repo.last_commit_at, "readme_text": repo.readme_text,
            "topics": repo.topics, "matched_keywords": mk,
            "productization_signal_count": sigs, "has_vertical_scene": vertical}


def _lab_stats(sess, lab):
    papers = sess.query(Paper).filter(Paper.lab_id == lab.id).all()
    kw_papers = [p for p in papers if (p.keywords_matched or "").strip()]
    directions = set()
    for p in papers:
        directions |= set((p.keywords_matched or "").split(","))
    directions.discard("")

    # 学生 + 高潜学生
    students = sess.query(Person).join(Authorship, Authorship.person_id == Person.id).join(
        Paper, Paper.id == Authorship.paper_id).filter(
        Paper.lab_id == lab.id, Person.is_student_candidate == True).distinct().all()  # noqa: E712
    hp = 0
    total_stars = 0
    repo_count = 0
    for s in students:
        links = sess.query(PersonRepoLink).filter(PersonRepoLink.person_id == s.id).all()
        repos = sess.query(Repo).filter(Repo.id.in_([l.repo_id for l in links])).all() if links else []
        stars = sum(r.stars or 0 for r in repos)
        total_stars += stars
        repo_count += len(repos)
        fa = sess.query(Authorship).filter(Authorship.person_id == s.id,
                                           Authorship.is_first_author == True).count()  # noqa: E712
        # 高潜学生:多产一作(≥2) 或 一作+有工程项目
        if fa >= 2 or (fa >= 1 and (repos or stars > 0)):
            hp += 1

    industry = sess.query(Relationship).filter(
        Relationship.source_type == "lab", Relationship.source_id == lab.id,
        Relationship.relation_type.in_(["COLLABORATES_WITH_COMPANY", "POTENTIAL_STARTUP_SIGNAL"])).count()
    has_company_coauthor = sess.query(Relationship).filter(
        Relationship.source_id == lab.id,
        Relationship.relation_type == "COLLABORATES_WITH_COMPANY").count() > 0

    return {
        "keyword_paper_count_3y": len(kw_papers), "total_stars": total_stars,
        "repo_count": repo_count, "high_potential_student_count": hp,
        "industry_signal_count": industry, "has_joint_lab": False,
        "has_industry_coauthor": has_company_coauthor, "directions": directions,
        "has_vertical_with_data": bool(directions & {"Recommendation", "Embodied AI",
                                                     "AI for Finance", "Data / Evaluation"}),
        "pi_has_company": False, "pi_has_joint_lab": False,
    }
