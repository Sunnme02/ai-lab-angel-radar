"""CSRankings 师资名册解析器(github.com/emeryberger/CSrankings,CC BY-NC-ND,研究用途)。

下载/缓存 26 个 csrankings-[a-z].csv(gh-pages 分支),解析为师资条目。
字段(实测表头):name, affiliation, homepage, scholarid, orcid。
只做数据层(取数+解析+缓存),业务过滤在 import_roster。
"""
import csv
import io
import os
import re
import string
import time

from ...utils.logging import get_logger
from ...utils.rate_limit import get_text

log = get_logger()
RAW = "https://raw.githubusercontent.com/emeryberger/CSrankings/gh-pages/csrankings-{}.csv"
CACHE_TTL_DAYS = 30
SCHOLAR_SENTINEL = "NOSCHOLARPAGE"
ORCID_SENTINEL = "0000-0000-0000-0000"


def _fresh(path):
    return os.path.exists(path) and (time.time() - os.path.getmtime(path)) < CACHE_TTL_DAYS * 86400


def _load_one(letter, cache_dir, refresh):
    """取单个 csrankings-{letter}.csv 的原始文本(缓存优先)。"""
    cp = os.path.join(cache_dir, f"csrankings-{letter}.csv")
    if not refresh and _fresh(cp):
        with open(cp, encoding="utf-8") as f:
            return f.read()
    try:
        text = get_text(RAW.format(letter), key="csrankings", per_sec=2)
    except Exception as e:  # noqa: BLE001
        log.warning(f"CSRankings 下载失败 {letter}: {e}")
        if os.path.exists(cp):  # 用旧缓存兜底
            with open(cp, encoding="utf-8") as f:
                return f.read()
        return ""
    os.makedirs(cache_dir, exist_ok=True)
    with open(cp, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def _parse(text):
    """按列名解析(CSV 列可能增减,务必 DictReader),处理哨兵值。"""
    out = []
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "name" not in reader.fieldnames or "affiliation" not in reader.fieldnames:
        return out
    for row in reader:
        name = (row.get("name") or "").strip()
        name = re.sub(r"\s+\d{4}$", "", name)   # 去掉 DBLP 同名消歧后缀 " 0001"
        aff = (row.get("affiliation") or "").strip()
        if not name or not aff:
            continue
        scholar = (row.get("scholarid") or "").strip()
        orcid = (row.get("orcid") or "").strip()
        out.append({
            "name": name,
            "affiliation": aff,
            "homepage": (row.get("homepage") or "").strip() or None,
            "scholar_id": None if scholar in ("", SCHOLAR_SENTINEL) else scholar,
            "orcid": None if orcid in ("", ORCID_SENTINEL) else orcid,
        })
    return out


def load_roster(cache_dir, refresh=False):
    """取全部 26 个文件,返回师资条目列表 [{name,affiliation,homepage,scholar_id,orcid}]。"""
    entries = []
    for letter in string.ascii_lowercase:
        entries.extend(_parse(_load_one(letter, cache_dir, refresh)))
    log.info(f"CSRankings 解析到师资 {len(entries)} 条")
    return entries
