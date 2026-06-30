"""导出 CSV(规格第13节)+ 触发图谱导出。"""
import json
import os

import pandas as pd

from .graph.build_graph import build_core_graph, build_graph
from .graph.export_graph import to_graphml, to_json, to_pyvis_html
from .models import (Lab, Paper, Person, Repo, Relationship, Score)
from .utils.logging import get_logger

log = get_logger()


def _df(sess, model):
    rows = [{c.name: getattr(o, c.name) for c in model.__table__.columns}
            for o in sess.query(model).all()]
    return pd.DataFrame(rows)


def export_all(db, sess, exports_dir):
    os.makedirs(exports_dir, exist_ok=True)
    exports_dir = os.path.abspath(exports_dir)
    data_dir = os.path.dirname(exports_dir)
    tables_dir = os.path.join(data_dir, "tables")
    graphs_dir = os.path.join(data_dir, "graphs")
    os.makedirs(tables_dir, exist_ok=True)
    os.makedirs(graphs_dir, exist_ok=True)

    def dump(model, name):
        df = _df(sess, model)
        df.to_csv(os.path.join(tables_dir, name), index=False)
        return len(df)

    n = {
        "labs.csv": dump(Lab, "labs.csv"),
        "people.csv": dump(Person, "people.csv"),
        "papers.csv": dump(Paper, "papers.csv"),
        "repos.csv": dump(Repo, "repos.csv"),
        "relationships.csv": dump(Relationship, "relationships.csv"),
    }

    # 分实体的 score CSV
    scores = _df(sess, Score)
    for et, fname in [("lab", "lab_scores.csv"), ("person", "person_scores.csv"),
                      ("repo", "repo_scores.csv")]:
        sub = scores[scores["entity_type"] == et] if not scores.empty else scores
        sub.to_csv(os.path.join(tables_dir, fname), index=False)
        n[fname] = len(sub)

    # 完整图(JSON/GraphML)放 data/graphs 供分析复用；exports 只留用户直接看的结果。
    G = build_graph(sess)
    to_json(G, os.path.join(graphs_dir, "graph.json"))
    try:
        to_graphml(G, os.path.join(graphs_dir, "graph.graphml"))
    except Exception as e:  # noqa: BLE001
        log.warning(f"GraphML 导出失败: {e}")
    core = build_core_graph(sess)
    try:
        to_pyvis_html(core, os.path.join(graphs_dir, "graph.html"))
    except Exception as e:  # noqa: BLE001
        log.warning(f"PyVis HTML 导出失败: {e}")
    n["graph"] = (f"完整 {G.number_of_nodes()}节点/{G.number_of_edges()}边 · "
                  f"核心图(可视化) {core.number_of_nodes()}节点/{core.number_of_edges()}边")

    log.info(f"导出完成: {json.dumps(n, ensure_ascii=False)}")
    return n
