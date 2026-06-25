"""图谱导出(规格 8.9):GraphML / JSON / PyVis 交互式 HTML。"""
import json

import networkx as nx

TYPE_COLOR = {"lab": "#e74c3c", "pi": "#e67e22", "person": "#3498db", "paper": "#95a5a6",
              "repo": "#2ecc71", "company": "#9b59b6", "keyword": "#f1c40f",
              "school": "#34495e"}


def to_json(G, path):
    data = nx.node_link_data(G, edges="links")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, default=str)


def to_graphml(G, path):
    H = G.copy()
    for _n, d in H.nodes(data=True):
        for k, v in list(d.items()):
            if isinstance(v, (list, dict)):
                d[k] = json.dumps(v, ensure_ascii=False)
            elif v is None:
                d[k] = ""
    for _u, _v, d in H.edges(data=True):
        for k, val in list(d.items()):
            if val is None:
                d[k] = ""
    nx.write_graphml(H, path)


def pyvis_html_string(G, height="640px"):
    """渲染为 HTML 字符串(供 Streamlit 内联),含图例。"""
    import os
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".html")
    os.close(fd)
    to_pyvis_html(G, path, height=height)
    with open(path, encoding="utf-8") as f:
        html = f.read()
    os.remove(path)
    return html


def to_pyvis_html(G, path, height="800px"):
    from pyvis.network import Network
    net = Network(height=height, width="100%", bgcolor="#ffffff", font_color="#222",
                  notebook=False, directed=False)
    net.barnes_hut(gravity=-18000, spring_length=200, spring_strength=0.02)
    for n, d in G.nodes(data=True):
        t = d.get("type", "?")
        sz = d.get("size") or (10 + (8 if t == "lab" else 4 if t == "person" else 0))
        sc = d.get("score")
        title = f"{t}: {d.get('label','')}" + (f" | score {sc}" if sc is not None else "")
        # 注意:不要传 group,否则 vis.js 会用自带调色板覆盖我们的 color(导致与图例不符)
        net.add_node(n, label=str(d.get("label", n))[:30], color=TYPE_COLOR.get(t, "#bbb"),
                     title=title, size=sz)
    for u, v, d in G.edges(data=True):
        conf = d.get("confidence")
        w = 1 + (conf * 6) if conf is not None else 1   # 置信度→边粗细
        rel = d.get("relation", "")
        title = rel + (f" (conf {conf})" if conf is not None else "")
        # 低置信师生边画虚线
        dashes = bool(conf is not None and conf < 0.6)
        net.add_edge(u, v, title=title, width=w, dashes=dashes)
    net.set_options('{"physics":{"stabilization":{"iterations":150}}}')
    net.save_graph(path)
    _inject_legend(path)


LEGEND_ITEMS = [("school", "学校"), ("lab", "实验室"), ("pi", "PI 导师"),
                ("person", "高潜学生"), ("repo", "GitHub 项目"), ("keyword", "方向关键词")]


def _inject_legend(path):
    """在 PyVis 生成的 HTML 里注入固定图例(PyVis 本身无图例)。"""
    rows = "".join(
        f'<div style="display:flex;align-items:center;margin:3px 0">'
        f'<span style="width:14px;height:14px;border-radius:50%;background:{TYPE_COLOR[t]};'
        f'display:inline-block;margin-right:8px"></span>{label}</div>'
        for t, label in LEGEND_ITEMS)
    # 边的图例:实线粗=高置信师生,虚线细=低置信疑似
    edge_rows = (
        '<div style="display:flex;align-items:center;margin:3px 0">'
        '<span style="width:26px;border-top:4px solid #888;display:inline-block;margin-right:8px"></span>'
        '实线/越粗 = 师生关系越确定</div>'
        '<div style="display:flex;align-items:center;margin:3px 0">'
        '<span style="width:26px;border-top:2px dashed #888;display:inline-block;margin-right:8px"></span>'
        '虚线/越细 = 低置信(疑似合作者)</div>')
    legend = (
        '<div style="position:fixed;top:14px;right:14px;z-index:9999;background:rgba(255,255,255,.95);'
        'border:1px solid #ccc;border-radius:8px;padding:10px 14px;font:13px/1.4 -apple-system,'
        'Segoe UI,sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.15)">'
        '<div style="font-weight:600;margin-bottom:6px">节点</div>' + rows +
        '<div style="margin-top:6px;color:#888;font-size:11px">节点越大=分数/stars 越高</div>'
        '<div style="font-weight:600;margin:8px 0 4px;border-top:1px solid #eee;padding-top:6px">连线</div>'
        + edge_rows + '</div>')
    try:
        with open(path, encoding="utf-8") as f:
            html = f.read()
        html = html.replace("</body>", legend + "</body>", 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception:  # noqa: BLE001
        pass
