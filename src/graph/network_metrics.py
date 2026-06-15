"""图谱中心性(规格 8.9):degree / betweenness / PageRank。返回 person 节点的归一中心性。"""
import networkx as nx


def compute_centrality(G):
    """返回 {person_id: {'degree','betweenness','pagerank','centrality'}}。

    centrality = 三者归一后的均值,用于学生评分的'网络中心性'维度。
    """
    if G.number_of_nodes() == 0:
        return {}
    deg = nx.degree_centrality(G)
    try:
        bet = nx.betweenness_centrality(G)
    except Exception:  # noqa: BLE001
        bet = {n: 0 for n in G}
    try:
        pr = nx.pagerank(G, max_iter=200)
    except Exception:  # noqa: BLE001
        pr = {n: 0 for n in G}

    def norm(d):
        mx = max(d.values()) if d else 1
        mx = mx or 1
        return {k: v / mx for k, v in d.items()}
    degn, betn, prn = norm(deg), norm(bet), norm(pr)

    out = {}
    for n, data in G.nodes(data=True):
        if data.get("type") != "person":
            continue
        pid = int(n.split(":")[1])
        c = (degn.get(n, 0) + betn.get(n, 0) + prn.get(n, 0)) / 3
        out[pid] = {"degree": round(degn.get(n, 0), 4),
                    "betweenness": round(betn.get(n, 0), 4),
                    "pagerank": round(prn.get(n, 0), 4),
                    "centrality": round(c, 4)}
    return out
