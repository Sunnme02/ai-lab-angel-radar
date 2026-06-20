"""合并多个 seed(手写 + CSRankings 等),按 (school, 规范化PI名) 去重。手写优先。"""
from ..utils.text import normalize_name


def merge_seeds(*seed_dicts):
    """输入多个 {schools:[...]} (先传的优先,其字段冲突时为准)。返回合并后的 {schools:[...]}。"""
    schools = {}      # name -> {name, aliases:set, labs: {norm_pi: lab_dict}}
    for sd in seed_dicts:
        if not sd:
            continue
        for sch in sd.get("schools", []):
            name = sch.get("name")
            if not name:
                continue
            entry = schools.setdefault(name, {"name": name, "aliases": set(), "labs": {}})
            for a in sch.get("aliases", []) or []:
                entry["aliases"].add(a)
            for lab in sch.get("labs", []) or []:
                key = normalize_name(lab.get("pi_name", ""))
                if not key:
                    continue
                if key not in entry["labs"]:
                    entry["labs"][key] = dict(lab)
                else:  # 已存在(更早=更优先):仅用新源补空字段
                    cur = entry["labs"][key]
                    for k, v in lab.items():
                        if v and not cur.get(k):
                            cur[k] = v
    out = []
    for entry in schools.values():
        out.append({"name": entry["name"], "aliases": sorted(entry["aliases"]),
                    "labs": list(entry["labs"].values())})
    return {"schools": out}
