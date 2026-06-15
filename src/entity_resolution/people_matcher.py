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
