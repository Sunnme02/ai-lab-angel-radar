"""AI Lab Angel Radar — Streamlit Dashboard(规格 8.10 的 6 页)。

运行:streamlit run app.py
"""
import json
import os
import sqlite3

import pandas as pd
import streamlit as st

from src.analysis import template_analysis
from src.config import Config

st.set_page_config(page_title="AI Lab Angel Radar", layout="wide")
CFG = Config()
DBP = CFG.db_path
EXPORTS = CFG.exports_dir


@st.cache_data(ttl=60)
def q(sql, params=()):
    con = sqlite3.connect(DBP)
    try:
        return pd.read_sql_query(sql, con, params=params)
    finally:
        con.close()


def scores_df(entity_type, score_name):
    df = q("SELECT entity_id, score_value, score_detail_json FROM scores "
           "WHERE entity_type=? AND score_name=?", (entity_type, score_name))
    return df


def detail(j):
    try:
        return json.loads(j)
    except Exception:  # noqa: BLE001
        return {}


st.sidebar.title("🛰️ AI Lab Angel Radar")
page = st.sidebar.radio("页面", ["首页", "实验室雷达", "学生雷达", "Repo 项目雷达",
                                 "定制图谱", "数据采集控制台"])

if not os.path.exists(DBP):
    st.warning("数据库尚未生成。请先运行 `python -m src.pipeline.run_all` 或用『数据采集控制台』。")
    st.stop()

# ---------------- 页面 1：首页 ----------------
if page == "首页":
    st.header("项目概览")
    st.caption("早期投资雷达:哪个实验室/学生/项目最可能在 6–24 个月形成可投 AI 初创?")
    c = st.columns(5)
    c[0].metric("学校", q("SELECT COUNT(DISTINCT school) n FROM labs")["n"][0])
    c[1].metric("实验室", q("SELECT COUNT(*) n FROM labs")["n"][0])
    c[2].metric("人物", q("SELECT COUNT(*) n FROM people")["n"][0])
    c[3].metric("论文", q("SELECT COUNT(*) n FROM papers")["n"][0])
    c[4].metric("Repo", q("SELECT COUNT(*) n FROM repos")["n"][0])
    upd = q("SELECT MAX(updated_at) t FROM labs")["t"][0]
    st.caption(f"数据更新时间:{upd}")
    if not CFG.has_github:
        st.info("提示:未配置 GITHUB_TOKEN,工程信号(repo/stars)未采集,工程化与学生评分会偏低。")

# ---------------- 页面 2：实验室雷达 ----------------
elif page == "实验室雷达":
    st.header("实验室雷达")
    labs = q("SELECT * FROM labs")
    sc = scores_df("lab", "angel_radar_score")
    rows = []
    for _, l in labs.iterrows():
        srow = sc[sc.entity_id == l["id"]]
        d = detail(srow["score_detail_json"].iloc[0]) if len(srow) else {}
        score = srow["score_value"].iloc[0] if len(srow) else 0
        pc = q("SELECT COUNT(*) n FROM papers WHERE lab_id=?", (int(l["id"]),))["n"][0]
        rows.append({"id": l["id"], "school": l["school"], "lab_name": l["lab_name"],
                     "pi_name": l["pi_name"], "keywords": l["keywords"],
                     "paper_count_3y": pc, "angel_radar_score": score,
                     "priority": d.get("priority", "")})
    df = pd.DataFrame(rows).sort_values("angel_radar_score", ascending=False)
    df.insert(0, "rank", range(1, len(df) + 1))

    cc = st.columns(3)
    schools = ["全部"] + sorted(df["school"].unique())
    fs = cc[0].selectbox("学校", schools)
    kw = cc[1].text_input("关键词过滤")
    rng = cc[2].slider("分数区间", 0, 100, (0, 100))
    view = df.copy()
    if fs != "全部":
        view = view[view.school == fs]
    if kw:
        view = view[view.keywords.str.contains(kw, case=False, na=False)]
    view = view[(view.angel_radar_score >= rng[0]) & (view.angel_radar_score <= rng[1])]
    st.dataframe(view[["rank", "school", "pi_name", "keywords", "paper_count_3y",
                       "angel_radar_score", "priority"]], use_container_width=True, hide_index=True)

    st.subheader("实验室详情卡片")
    pick = st.selectbox("选择实验室", view["pi_name"].tolist())
    if pick:
        lrow = df[df.pi_name == pick].iloc[0]
        lid = int(lrow["id"])
        srow = sc[sc.entity_id == lid]
        d = detail(srow["score_detail_json"].iloc[0]) if len(srow) else {}
        st.markdown(f"### {pick} · {lrow['school']}  —  Angel Radar Score **{lrow['angel_radar_score']}** ({d.get('priority','')})")
        st.markdown(f"**方向关键词**:{lrow['keywords']}")
        cols = st.columns(2)
        with cols[0]:
            st.markdown("**评分细节**")
            for k, v in d.get("dimensions", {}).items():
                st.markdown(f"- `{v['score']}` {k} — {v['reason']}")
        with cols[1]:
            st.markdown("**代表论文(按引用)**")
            pp = q("SELECT title,year,citation_count FROM papers WHERE lab_id=? "
                   "ORDER BY citation_count DESC LIMIT 6", (lid,))
            for _, p in pp.iterrows():
                st.markdown(f"- [{p['year']}] {str(p['title'])[:70]} · cite {p['citation_count']}")
            st.markdown("**核心学生(一作高产)**")
            stu = q("""SELECT pe.name, COUNT(*) fa FROM authorships a
                       JOIN papers pa ON pa.id=a.paper_id JOIN people pe ON pe.id=a.person_id
                       WHERE pa.lab_id=? AND a.is_first_author=1 AND pe.is_pi=0
                       GROUP BY pe.id ORDER BY fa DESC LIMIT 6""", (lid,))
            for _, s in stu.iterrows():
                st.markdown(f"- {s['name']} · 一作 {s['fa']} 篇")
        # 自动分析
        directions = []
        for p in q("SELECT keywords_matched FROM papers WHERE lab_id=?", (lid,))["keywords_matched"].dropna():
            directions += [x for x in str(p).split(",") if x]
        top_dir = [x for x, _ in pd.Series(directions).value_counts().head(4).items()]
        st.markdown("**🧠 自动投资分析**")
        st.text(template_analysis({}, q("""SELECT pe.name FROM authorships a JOIN papers pa ON pa.id=a.paper_id
            JOIN people pe ON pe.id=a.person_id WHERE pa.lab_id=? AND a.is_first_author=1 AND pe.is_pi=0
            GROUP BY pe.id ORDER BY COUNT(*) DESC LIMIT 4""", (lid,))["name"].tolist(),
            top_dir, [], d))

# ---------------- 页面 3：学生雷达 ----------------
elif page == "学生雷达":
    st.header("学生雷达")
    sc = scores_df("person", "student_startup_score")
    rows = []
    for _, s in sc.iterrows():
        pid = int(s["entity_id"])
        pe = q("SELECT name,affiliation,role FROM people WHERE id=? AND is_pi=0 "
               "AND is_student_candidate=1", (pid,))
        if not len(pe):
            continue  # 排除 PI / 非学生候选
        d = detail(s["score_detail_json"])
        fa = q("SELECT COUNT(*) n FROM authorships WHERE person_id=? AND is_first_author=1", (pid,))["n"][0]
        rp = q("SELECT COUNT(*) n FROM authorships WHERE person_id=?", (pid,))["n"][0]
        rows.append({"name": pe["name"][0], "affiliation": pe["affiliation"][0], "role": pe["role"][0],
                     "first_author": fa, "related_papers": rp,
                     "person_score": s["score_value"], "contact_priority": d.get("contact_priority", "")})
    df = pd.DataFrame(rows).sort_values("person_score", ascending=False)
    df.insert(0, "rank", range(1, len(df) + 1))
    st.dataframe(df.head(100), use_container_width=True, hide_index=True)

# ---------------- 页面 4：Repo 项目雷达 ----------------
elif page == "Repo 项目雷达":
    st.header("Repo 项目雷达")
    repos = q("SELECT * FROM repos")
    if repos.empty:
        st.info("暂无 repo 数据(需配置 GITHUB_TOKEN 后重新采集)。")
    else:
        sc = scores_df("repo", "productization_score")
        repos = repos.merge(sc.rename(columns={"entity_id": "id", "score_value": "productization_score"}),
                            on="id", how="left")
        repos = repos.sort_values("productization_score", ascending=False)
        st.dataframe(repos[["repo_name", "owner", "stars", "forks", "language", "topics",
                            "matched_keywords", "last_commit_at", "productization_score"]],
                     use_container_width=True, hide_index=True)

# ---------------- 页面 5：定制图谱(按需子图)----------------
elif page == "定制图谱":
    st.header("定制图谱")
    st.caption("输入老师/方向/学校,只看相关的那张子图(避免全图毛球)。")
    import sqlite3 as _sq

    from src.graph.export_graph import pyvis_html_string
    from src.graph import query as gq

    mode = st.radio("查询方式", ["按老师(恒星)", "按方向", "按学校"], horizontal=True)
    con = _sq.connect(DBP)
    from src.db import DB
    _db = DB(DBP)
    with _db.session() as sess:
        G = None
        caption = ""
        if mode == "按老师(恒星)":
            pis = [r[0] for r in con.execute("SELECT pi_name FROM labs ORDER BY pi_name")]
            pi = st.selectbox("选老师(作为恒星中心)", pis)
            k = st.slider("最多显示学生数", 5, 60, 30)
            if pi:
                G = gq.ego_pi(sess, pi, max_students=k)
                caption = f"以 **{pi}** 为中心的师承网络"
        elif mode == "按方向":
            dirs = gq.all_directions(sess)
            d = st.selectbox("选方向(或下方自定义)", dirs)
            d2 = st.text_input("或自定义方向关键词(留空则用上面)", "")
            direction = d2.strip() or d
            n = st.slider("最多显示实验室数", 5, 30, 15)
            if direction:
                G, total = gq.by_direction(sess, direction, max_labs=n)
                caption = f"方向 **{direction}**:共命中 {total} 个实验室,显示前 {min(n, total)} 个"
        else:
            schools = [r[0] for r in con.execute("SELECT DISTINCT school FROM labs")]
            sc = st.selectbox("选学校", schools)
            if sc:
                G = gq.by_school(sess, sc)
                caption = f"**{sc}** 的 AI 师承网络"

        if G is not None and G.number_of_nodes() > 0:
            st.markdown(caption + f"  ·  {G.number_of_nodes()} 节点 / {G.number_of_edges()} 边")
            st.components.v1.html(pyvis_html_string(G), height=680, scrolling=True)
        else:
            st.info("无匹配结果,换个老师/方向试试。")
    con.close()

# ---------------- 页面 6：数据采集控制台 ----------------
elif page == "数据采集控制台":
    st.header("数据采集控制台")
    st.caption("输入单个 PI 触发采集(会写入同一数据库)。大批量建议用命令行 `python -m src.pipeline.run_all`。")
    with st.form("collect"):
        pi = st.text_input("PI name", "Weinan Zhang")
        school = st.text_input("School", "Shanghai Jiao Tong University")
        kw = st.text_input("Keywords(逗号分隔)", "LLM,Agent,Recommendation,LoRA")
        homepage = st.text_input("Homepage URL(可选)", "")
        go = st.form_submit_button("运行采集 pipeline")
    if go:
        from src.pipeline.core import Context, finalize, process_lab
        with st.spinner(f"采集 {pi} @ {school} …"):
            ctx = Context(CFG)
            process_lab(ctx, school, {"pi_name": pi, "homepage_url": homepage or None,
                                      "keywords": [k.strip() for k in kw.split(",") if k.strip()]})
            summary = finalize(ctx)
        st.success(f"完成:{summary}")
        st.cache_data.clear()
