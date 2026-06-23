"""师资名册导入器:CSRankings 名单 → 学校匹配 → OpenAlex AI 过滤 → 生成 seed yaml。

用法:
  python -m src.pipeline.import_roster \
    --schools "Tsinghua University,Peking University,Fudan University,Shanghai Jiao Tong University" \
    --max-per-school 25 --out data/seeds/labs_seed_csrankings.yaml
"""
import argparse
import json
import os

import yaml

from ..classifiers.keyword_classifier import classify_text
from ..collectors.academic.csrankings import load_roster
from ..collectors.academic.openalex import OpenAlexCollector
from ..config import ROOT, Config
from ..utils.logging import get_logger
from ..utils.text import normalize_name

log = get_logger()
CONFUSABLE = {"shanghaitech university"}   # 与 "Shanghai Jiao Tong" 易混,显式排除


def _target_schools(arg, cfg):
    """目标学校:命令行 --schools 优先,否则取手写 seed 的 schools[].name(+aliases)。"""
    seeds = cfg.load_seeds()
    alias_map = {s["name"]: (s.get("aliases") or []) for s in seeds.get("schools", [])}
    if arg:
        names = [x.strip() for x in arg.split(",") if x.strip()]
        return {n: alias_map.get(n, []) for n in names}
    return alias_map


def _match_school(affiliation, targets):
    """affiliation 精确(大小写无关)匹配目标学校;排除混淆项。返回规范 school.name 或 None。"""
    aff = (affiliation or "").strip()
    if aff.casefold() in CONFUSABLE:
        return None
    for name in targets:
        if aff.casefold() == name.casefold():
            return name
    return None


def _load_oa_cache(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schools", default=None, help="逗号分隔;默认取手写 seed 的学校")
    ap.add_argument("--max-per-school", type=int, default=25)
    ap.add_argument("--no-ai-filter", action="store_true", help="跳过 OpenAlex 领域过滤(调试)")
    ap.add_argument("--refresh-cache", action="store_true")
    ap.add_argument("--out", default="data/seeds/labs_seed_csrankings.yaml")
    ap.add_argument("--config", default=None)
    a = ap.parse_args()

    cfg = Config(a.config)
    cache_dir = str(ROOT / cfg.settings["paths"].get("csrankings_cache", "data/raw/csrankings"))
    targets = _target_schools(a.schools, cfg)
    log.info(f"目标学校: {list(targets)}")

    # 1) CSRankings 全量 → 命中目标校
    roster = load_roster(cache_dir, refresh=a.refresh_cache)
    by_school = {n: [] for n in targets}
    for e in roster:
        sch = _match_school(e["affiliation"], targets)
        if sch:
            by_school[sch].append(e)
    for n, lst in by_school.items():
        log.info(f"  {n}: CSRankings 命中 {len(lst)} 人")

    # 2) OpenAlex AI 过滤(带缓存)
    oa = OpenAlexCollector(email=cfg.openalex_email, cache_dir=cfg.openalex_cache_dir)
    oa_cache_path = os.path.join(cache_dir, "oa_classify_cache.json")
    oa_cache = {} if a.refresh_cache else _load_oa_cache(oa_cache_path)

    def classify(name, school, orcid=None):
        if a.no_ai_filter:
            return {"is_cs": True, "top_topics": [], "works_count": 0}
        key = f"{normalize_name(name)}|{school}|{orcid or ''}"
        if key in oa_cache:
            return oa_cache[key]
        res = oa.classify_author(name, school, orcid=orcid)  # 有 ORCID 则精确直查,零串人
        oa_cache[key] = res        # 可能为 None,也缓存(避免重复查)
        return res

    schools_out = []
    for school, entries in by_school.items():
        kept = []
        for e in entries:
            res = classify(e["name"], school, e.get("orcid"))
            if not res or not res.get("is_cs"):
                continue
            kept.append((e, res))
        # 按 works_count 降序截断
        kept.sort(key=lambda x: (x[1] or {}).get("works_count", 0), reverse=True)
        kept = kept[:a.max_per_school]
        labs = []
        for e, res in kept:
            kws = []
            for t in (res.get("top_topics") or []):
                kws.extend(classify_text(t))
            scholar_url = (f"https://scholar.google.com/citations?user={e['scholar_id']}"
                           if e.get("scholar_id") else None)
            labs.append({
                "pi_name": e["name"], "pi_name_cn": None,
                "homepage_url": e.get("homepage"),
                "keywords": sorted(set(kws)),
                "scholar_url": scholar_url,
                "orcid": e.get("orcid"),     # ORCID 锚点:pipeline 用它精确锁定作者
                "source_url": "https://csrankings.org",
            })
        schools_out.append({"name": school, "aliases": targets[school], "labs": labs})
        log.info(f"  {school}: AI 过滤后保留 {len(labs)} 人")

    # 3) 写缓存 + seed
    os.makedirs(cache_dir, exist_ok=True)
    with open(oa_cache_path, "w", encoding="utf-8") as f:
        json.dump(oa_cache, f, ensure_ascii=False)
    out_path = a.out if os.path.isabs(a.out) else str(ROOT / a.out)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# 自动生成(CSRankings + OpenAlex 领域过滤),勿手改。\n")
        yaml.safe_dump({"schools": schools_out}, f, allow_unicode=True, sort_keys=False)
    total = sum(len(s["labs"]) for s in schools_out)
    log.info(f"已写出 {total} 位 AI 老师 -> {out_path}")


if __name__ == "__main__":
    main()
