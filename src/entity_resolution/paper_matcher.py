"""论文去重(规格 8.6):以规范化标题为主键。"""
from ..models import Paper
from ..utils.text import normalize_title


def find_or_create_paper(db, sess, lab_id, paper: dict):
    """按 (规范化标题, lab_id) upsert 论文。返回 Paper。"""
    norm = normalize_title(paper.get("title") or "")
    if not norm:
        return None
    values = {
        "title": paper.get("title"),
        "year": paper.get("year"),
        "venue": paper.get("venue"),
        "abstract": paper.get("abstract"),
        "url": paper.get("url"),
        "pdf_url": paper.get("pdf_url"),
        "source": paper.get("source"),
        "citation_count": paper.get("citation_count", 0),
        "keywords_matched": ",".join(paper.get("keywords_matched", []) or []),
    }
    return db.upsert(sess, Paper, {"norm_title": norm, "lab_id": lab_id}, values)
