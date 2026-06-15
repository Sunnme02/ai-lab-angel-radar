# AI Lab Angel Radar · AI 实验室早期创业雷达

自动从公开数据源发现中国顶尖高校 AI 实验室中**潜在的早期创业机会**,输出实验室/学生/项目雷达 + 关系图谱 + Angel Radar 评分排名。

> 核心问题:**哪个实验室、哪个学生、哪个项目,最可能在未来 6–24 个月形成一个可投的 AI 初创公司?**

## 1. 项目介绍
输入「学校 + 技术关键词 + 年份」,系统自动:采集近三年论文(OpenAlex/S2)→ 识别核心学生与一作 → 匹配 GitHub 工程项目 → 分类方向与创业信号 → 规则评分 → 构建关系图谱 → 在 Streamlit Dashboard 呈现排名与分析。

## 2. 项目架构
```
src/
  config.py            读取 .env / settings.yaml / labs_seed.yaml
  db.py, models.py     SQLite + SQLAlchemy(9 张表,带 created/updated_at + upsert 去重)
  collectors/
    academic/          openalex / semantic_scholar / dblp / openreview
    web/               homepage / search / news
    github/            github_api / repo_matcher(带 confidence)
  entity_resolution/   people / org / paper 消歧(保留 confidence)
  classifiers/         keyword_classifier / startup_signal_classifier(规则法)
  scoring/             lab / person / repo 评分(每分带 explanation)
  graph/               build_graph / network_metrics(degree/betweenness/PageRank) / export(GraphML/JSON/PyVis)
  pipeline/            core(编排)/ run_all / run_lab
  analysis.py          自动投资分析(模板;有 LLM key 可换 LLM)
app.py                 Streamlit Dashboard(6 页)
```

## 3. 安装
```bash
python -m venv venv && source venv/bin/activate   # 可选
pip install -r requirements.txt
cp .env.example .env                              # 按需填写
```

## 4. 环境变量(`.env`)
| 变量 | 是否必须 | 说明 |
|---|---|---|
| `OPENALEX_EMAIL` | 建议 | 进入 OpenAlex polite pool(更快更稳) |
| `GITHUB_TOKEN` | **强烈建议** | 免费 PAT;无则跳过 GitHub 采集,工程/学生评分偏低 |
| `SEMANTIC_SCHOLAR_API_KEY` | 可选 | 提高 S2 限流额度 |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | 可选 | 生成 LLM 版投资分析;无则用模板 |

## 5. 运行 pipeline
```bash
# 跑全部 seed labs(configs/settings.yaml + data/seeds/labs_seed.yaml)
python -m src.pipeline.run_all

# 只跑前 N 个 lab(调试)
python -m src.pipeline.run_all --limit-labs 2

# 跑单个 PI
python -m src.pipeline.run_lab --pi "Xipeng Qiu" --school "Fudan University" --keywords "LLM,PEFT,LoRA"
```
产物:`data/radar.db`(SQLite)+ `data/exports/*.csv` + `graph.json/.html`。

## 6. 启动 Dashboard
```bash
streamlit run app.py
```
6 个页面:首页 / 实验室雷达 / 学生雷达 / Repo 项目雷达 / 关系图谱 / 数据采集控制台。

## 7. 数据来源
- 学术:OpenAlex(主)、Semantic Scholar(补 h-index)、DBLP、OpenReview。
- 工程:GitHub API(repo/stars/README/topics)。
- 网页:导师/实验室主页(成员与产业信号)、DuckDuckGo 轻量搜索(新闻线索)。
- 第一版只用**公开数据**,不接付费数据库。

## 8. 评分体系(规则法,均带 explanation)
- **实验室 Angel Radar Score(100)**:技术前沿15 / 工程化20 / 学生潜力20 / 产业连接15 / 数据闭环15 / 商业防御10 / 导师支持5。
- **学生创业潜力(100)**:论文20 / 工程25 / 前沿匹配15 / 产品化15 / 产业连接10 / 网络中心性10 / 创业窗口5。
- **Repo 产品化(100)**:活跃20 / 社区20 / 产品化20 / 前沿20 / 商业场景20。
- 每个分都写入 `score_detail_json`,Dashboard 展示分数来源。

## 9. 置信度说明
- GitHub repo ↔ 人 的匹配保留 `confidence`(主页直链=1.0,用户名命中=0.9,README 提论文=0.85,fuzzy=0.6;<0.6 仅作 candidate)。
- 人物消歧:OpenAlex id 一致 / 同名+机构相近才合并;同名异机构不合并。
- 低置信匹配不当作事实,Dashboard 标注来源与置信度。

## 10. 当前局限
- 无 `GITHUB_TOKEN` 时工程/学生信号严重偏低。
- 角色识别弱(一作默认 PhD 候选,其余 Unknown,不强行打高分)。
- 学生/PI 重名仍可能误判(已用机构 + 计算机领域加权降低,但非零)。
- "即将创业/隐身公司"无法靠公开搜索发现(见路线图 v0.4 工商监控)。
- 第一版优先**可运行**,不追求完美召回。

## 11. 后续路线图
- v0.2:自动发现更多实验室、HF/ModelScope、高校成员页抽取、中文新闻、更强消歧。
- v0.3:Neo4j、LLM 信息抽取、投资 memo 自动生成、周度自动更新。
- v0.4:公司注册/融资数据(企查查等)、校友创业图谱、投资人网络、"即将创业学生"信号监控。
