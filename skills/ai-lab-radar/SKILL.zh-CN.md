---
name: ai-lab-radar
description: 通用 AI 方向雷达技能：给定任意 AI 方向、关键词或教授名字，使用本地 ai-lab-angel-radar 项目检索实验室/教授/学生/项目信号，生成可解释关系图谱和简洁观察清单。
---

# AI Lab Radar

这个 skill 用在 `ai-lab-angel-radar` 仓库里。它不应该只服务 World Model，而应该服务任何 AI 方向，例如 Agent、World Model、Multimodal、Embodied AI、AI Infra、推荐系统、模型压缩、自动驾驶等。

## 目标

输入一个方向或老师，输出一张可解释的关系图谱和一份简洁判断：

- 这个方向里哪些教授/实验室最相关。
- 每个教授下面有哪些学生节点。
- 学生之间是否有合作关系。
- 纳入依据是什么：方向关键词、论文标题、实验室关键词、分数、关系边。
- 哪些节点值得后续人工深挖。

## 先判断用户意图

把用户请求归到下面一种：

- **方向检索**：用户给一个方向，例如 `Agent`、`World Model`、`VLA`、`AI Infra`。
- **教授检索**：用户给一个老师，例如 `Xipeng Qiu`。
- **图谱导出**：用户要 HTML/JSON/GraphML 产物。
- **项目整理**：用户要开源、API 化、skill 化、文档化。

如果用户只给方向，不要急着问很多问题。先用这个方向本身作为关键词，再根据需要扩展 3-8 个近义词。
如果项目配置了 LLM key，可以优先调用 `src.llm.expand_direction` 扩展关键词；没有 key 时使用内置模板或人工补充关键词。

## 通用方向工作流

1. 规范化方向：
   - 保留用户原始方向名。
   - 生成关键词列表，例如 `Agent` 可以扩成 `AI Agent`、`LLM Agent`、`multi-agent`、`tool use`、`planning`。
   - 如果方向已有固定关键词模板，可以直接使用模板；否则用用户给定方向和近义词。
2. 查询本地数据库：
   - 查 `labs.keywords`。
   - 查 `papers.title`、`papers.keywords_matched`、必要时查 `papers.abstract`。
   - 不要把所有论文作者全部展开成毛球。
3. 选取核心节点：
   - 先选相关实验室/教授。
   - 每个教授只展开少量高置信学生。
   - 需要看单个老师时，用恒星图。
4. 生成图谱：
   - 方向图：方向 → 教授/实验室 → 学生/学校。
   - 教授图：老师居中 → 学生环绕 → 学生间共同论文。
5. 输出解释：
   - 说明匹配依据。
   - 说明边的含义。
   - 明确哪些关系是推断关系，可能有噪声。

## 当前可用命令

生成任意 AI 方向图：

```bash
python -m src.graph.export_direction_graph --direction "Agent" --keywords "AI Agent,LLM Agent,multi-agent,tool use,planning"
```

生成某个老师的恒星图：

```bash
python -m src.graph.export_pi_ego_graph --pi "Xipeng Qiu" --max-students 16
```

可选：用 LLM 或规则模板扩展方向关键词：

```bash
python -m src.llm.expand_direction --direction "世界模型"
```

可选：审查图谱关系。没有 LLM key 时可以加 `--no-llm` 生成规则版审查报告。

```bash
python -m src.llm.audit_graph --input data/exports/pi_ego_xipeng_qiu.json
```

可选：生成中文分析 memo。memo 只能基于图谱 JSON 中已有证据，不应补造事实。

```bash
python -m src.llm.write_memo --input data/exports/direction_graph_agent.json
```

启动 Dashboard：

```bash
streamlit run app.py
```

启动可选本地 API。本地 API 是给网页、LLM 或 skill 调用本项目能力的本机接口；不启动也可以直接用上面的命令。

```bash
uvicorn src.api:app --reload
```

运行测试：

```bash
pytest -q
```

## 当前 API

API 服务启动后，可以使用这些接口：

- `POST /directions/graph/export`
- `POST /professors/{name}/ego/export`

其中 `/directions/graph/export` 是通用方向图谱入口。

兼容旧 World Model 图谱的接口还在，但不作为 skill 的主入口：

- `GET /world-model/directions`
- `GET /world-model/directions/{direction}`
- `GET /world-model/professors/{name}`
- `POST /world-model/export`

后续可继续扩展成：

- `POST /directions/search`
- `POST /professors/search`
- `POST /professors/{name}/ego/export`

## 图谱设计约定

方向总览图：

- 方向节点：用户给定方向。
- 教授节点：命中方向的 PI。
- 学生节点：高置信学生/潜在创业节点。
- 学校节点：归属上下文。
- 论文只作为证据，不默认进入图节点。

老师恒星图：

- 老师固定在中心。
- 学生围成一圈。
- 紫线：老师-学生合作/指导。
- 灰线：学生-学生共同论文。
- 学生点越绿，代表学生分数越高。

## 输出格式

方向检索时，回答应包含：

- 方向名和关键词。
- 命中的教授/实验室。
- 学生分支概览。
- 主要证据。
- HTML/JSON 产物路径。
- 后续人工深挖优先级。

教授检索时，回答应包含：

- 教授、学校、实验室。
- 学生名单。
- 主要合作/共同论文结构。
- HTML 图谱路径。
- 关系噪声提醒。

如果运行了 LLM 审查或 memo，回答还应说明：

- LLM 只做审查和表达，不是底层事实来源。
- 哪些关系是高置信推断。
- 哪些关系需要人工复核。
- 生成的审查报告或 memo 路径。

## 安全要求

不要暴露：

- `.env`
- token/API key
- `data/radar.db`
- 未发布的 raw/cache 文件

除非用户明确说已经准备公开，否则把图谱输出视为本地派生产物。
