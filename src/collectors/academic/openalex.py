"""OpenAlex 采集器:按 PI 找作者 → 取近三年论文 → 抽作者/机构/引用/摘要。

主力学术源。免费、有 polite pool(带 mailto)。所有查询落盘缓存,避免重复砸 API 触发限流。
"""
import hashlib
import json
import os

from rapidfuzz import fuzz

from ...utils.logging import get_logger
from ...utils.rate_limit import get_json
from ...utils.text import restore_abstract

log = get_logger()
BASE = "https://api.openalex.org"
SELECT_WORK = ("id,doi,display_name,publication_year,cited_by_count,authorships,"
               "abstract_inverted_index,keywords,concepts,primary_location,"
               "primary_topic,best_oa_location")


def _is_cs_author(author_json):
    """看 OpenAlex 作者 topics 的 field/domain 是否属计算机/AI 领域。"""
    for t in (author_json.get("topics") or [])[:5]:
        field = (t.get("field") or {}).get("display_name") or ""
        domain = (t.get("domain") or {}).get("display_name") or ""
        if ("Computer Science" in field or "Computer Science" in domain
                or "Artificial Intelligence" in field):
            return True
    return False


class OpenAlexCollector:
    def __init__(self, email: str = "", cache_dir: str = None):
        self.email = email
        self.cache_dir = cache_dir
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    def _cache_get(self, key):
        if not self.cache_dir:
            return None
        fp = os.path.join(self.cache_dir, hashlib.md5(key.encode()).hexdigest() + ".json")
        if os.path.exists(fp):
            try:
                with open(fp, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:  # noqa: BLE001
                return None
        return None

    def _cache_put(self, key, val):
        if not self.cache_dir:
            return
        fp = os.path.join(self.cache_dir, hashlib.md5(key.encode()).hexdigest() + ".json")
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(val, f, ensure_ascii=False)

    def _params(self, **kw):
        p = {"mailto": self.email} if self.email else {}
        p.update(kw)
        return p

    def author_by_orcid(self, orcid: str):
        """用 ORCID 精确直查作者(全球唯一,零串人)。返回 author json 或 None。缓存。"""
        if not orcid:
            return None
        oc = orcid.replace("https://orcid.org/", "").strip()
        ck = f"orcid|{oc}"
        cached = self._cache_get(ck)
        if cached is not None:
            return cached
        try:
            a = get_json(f"{BASE}/authors/https://orcid.org/{oc}", key="openalex", per_sec=3,
                         params=self._params(
                             select="id,display_name,works_count,last_known_institutions,topics"))
            self._cache_put(ck, a)
            return a
        except Exception as e:  # noqa: BLE001
            log.debug(f"OpenAlex ORCID 查询失败 {orcid}: {e}")
            return None

    def find_author(self, pi_name: str, affiliation: str = "", orcid: str = None):
        """定位作者:有 ORCID 则精确直查(零串人);否则按姓名搜(强约束 + 领域/机构加权)。

        返回 (author_id, display_name)。
        """
        if orcid:
            a = self.author_by_orcid(orcid)
            if a:
                return a["id"], a.get("display_name")
        ck = f"find|{pi_name.lower()}|{(affiliation or '').lower()}"
        cached = self._cache_get(ck)
        if cached is not None:
            return tuple(cached)
        try:
            d = get_json(f"{BASE}/authors", key="openalex", per_sec=3,
                         params=self._params(
                             search=pi_name, per_page=25,
                             select="id,display_name,works_count,last_known_institutions,topics"))
        except Exception as e:  # noqa: BLE001
            log.warning(f"OpenAlex 找作者失败 {pi_name}: {e}")
            return None, None
        results = d.get("results", [])
        if not results:
            return None, None

        best, best_score = None, -1
        for a in results:
            disp = a.get("display_name", "")
            name_score = fuzz.WRatio(pi_name.lower(), disp.lower())
            if name_score < 80:               # 姓名不够像 → 大概率是别人(如 Wei Zhang)
                continue
            insts = a.get("last_known_institutions") or []
            inst_names = " ".join(i.get("display_name", "") for i in insts)
            aff_score = fuzz.partial_ratio(affiliation.lower(), inst_names.lower()) if affiliation else 0
            cs = 1 if _is_cs_author(a) else 0
            score = name_score * 2 + aff_score * 2 + cs * 120 + a.get("works_count", 0) / 1000.0
            if score > best_score:
                best, best_score = a, score
        if best:
            res = (best["id"], best.get("display_name"))
            self._cache_put(ck, list(res))
            return res
        return None, None

    def classify_author(self, pi_name: str, affiliation: str = "", orcid: str = None):
        """同 find_author 选出 best,但额外返回领域判定。

        有 ORCID 则精确直查(零串人);否则按姓名搜。
        返回 {author_id, display_name, is_cs, top_topics, works_count} 或 None。
        供师资名册"只留 AI 老师"过滤用。
        """
        if orcid:
            a = self.author_by_orcid(orcid)
            if a:
                return {
                    "author_id": a["id"], "display_name": a.get("display_name"),
                    "is_cs": _is_cs_author(a),
                    "top_topics": [t.get("display_name") for t in (a.get("topics") or [])[:5]],
                    "works_count": a.get("works_count", 0),
                }
        try:
            d = get_json(f"{BASE}/authors", key="openalex", per_sec=5,
                         params=self._params(
                             search=pi_name, per_page=25,
                             select="id,display_name,works_count,last_known_institutions,topics"))
        except Exception as e:  # noqa: BLE001
            log.warning(f"OpenAlex classify 失败 {pi_name}: {e}")
            return None
        best, best_score = None, -1
        for a in d.get("results", []):
            disp = a.get("display_name", "")
            name_score = fuzz.WRatio(pi_name.lower(), disp.lower())
            if name_score < 80:
                continue
            insts = a.get("last_known_institutions") or []
            inst_names = " ".join(i.get("display_name", "") for i in insts)
            aff_score = fuzz.partial_ratio(affiliation.lower(), inst_names.lower()) if affiliation else 0
            cs = 1 if _is_cs_author(a) else 0
            score = name_score * 2 + aff_score * 2 + cs * 120 + a.get("works_count", 0) / 1000.0
            if score > best_score:
                best, best_score = a, score
        if not best:
            return None
        return {
            "author_id": best["id"],
            "display_name": best.get("display_name"),
            "is_cs": _is_cs_author(best),
            "top_topics": [t.get("display_name") for t in (best.get("topics") or [])[:5]],
            "works_count": best.get("works_count", 0),
        }

    def get_works_by_author(self, author_id: str, year_from: int, year_to: int, max_papers=60):
        """取作者在年份区间的论文(按引用降序),分页。缓存(非空才存)。"""
        short = author_id.rstrip("/").split("/")[-1]
        ck = f"works|{short}|{year_from}|{year_to}|{max_papers}"
        cached = self._cache_get(ck)
        if cached is not None:
            return cached
        works, cursor = [], "*"
        while len(works) < max_papers:
            try:
                d = get_json(f"{BASE}/works", key="openalex", per_sec=3,
                             params=self._params(
                                 filter=f"authorships.author.id:{short},"
                                        f"publication_year:{year_from}-{year_to}",
                                 sort="cited_by_count:desc", per_page=50, cursor=cursor,
                                 select=SELECT_WORK))
            except Exception as e:  # noqa: BLE001
                log.warning(f"OpenAlex 取论文失败: {e}")
                break
            batch = d.get("results", [])
            if not batch:
                break
            works.extend(batch)
            cursor = d.get("meta", {}).get("next_cursor")
            if not cursor:
                break
        parsed = [self._parse_work(w) for w in works[:max_papers]]
        if parsed:                     # 非空才缓存(避免把限流导致的空结果缓存)
            self._cache_put(ck, parsed)
        return parsed

    def _parse_work(self, w):
        authors = []
        for a in w.get("authorships", []):
            au = a.get("author", {}) or {}
            insts = [{"name": i.get("display_name"), "country": i.get("country_code"),
                      "ror": i.get("ror")} for i in a.get("institutions", [])]
            authors.append({
                "name": au.get("display_name") or a.get("raw_author_name"),
                "openalex_author_id": au.get("id"),
                "order": {"first": 1, "middle": 2, "last": 3}.get(a.get("author_position"), 2),
                "author_position": a.get("author_position"),
                "is_corresponding": bool(a.get("is_corresponding")),
                "institutions": insts,
            })
        kws = [k.get("display_name") for k in (w.get("keywords") or [])]
        if not kws:
            kws = [c.get("display_name") for c in (w.get("concepts") or [])[:6]]
        loc = w.get("primary_location") or {}
        oa_loc = w.get("best_oa_location") or {}
        return {
            "title": w.get("display_name"),
            "year": w.get("publication_year"),
            "venue": (loc.get("source") or {}).get("display_name"),
            "abstract": restore_abstract(w.get("abstract_inverted_index")),
            "url": loc.get("landing_page_url") or w.get("doi"),
            "pdf_url": oa_loc.get("pdf_url"),
            "citation_count": w.get("cited_by_count", 0),
            "source": "openalex",
            "authors": authors,
            "concepts": kws,
        }

    def collect_lab(self, pi_name, affiliation, year_from, year_to, max_papers=60, orcid=None):
        aid, disp = self.find_author(pi_name, affiliation, orcid=orcid)
        if not aid:
            log.warning(f"未在 OpenAlex 找到 {pi_name}@{affiliation}")
            return aid, []
        log.info(f"OpenAlex 命中作者 {disp} ({aid.split('/')[-1]}) for {pi_name}")
        return aid, self.get_works_by_author(aid, year_from, year_to, max_papers)
