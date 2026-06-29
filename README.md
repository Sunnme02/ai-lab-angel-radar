# AI Lab Angel Radar

An open-source radar for AI lab discovery. Give it an AI direction or a professor
name, and it builds a focused knowledge graph of professors, students, schools
and relationship evidence.

The project is designed for early technical scouting: finding which labs,
students and research lines may be worth deeper follow-up.

## Two Core Workflows

### 1. Search By Direction

Input an AI direction such as `Agent`, `World Model`, `VLA`, `AI Infra`,
`Multimodal`, or `Autonomous Driving`. The tool searches lab keywords and paper
evidence, then outputs a focused direction graph:

- direction -> professor
- professor -> student
- school -> professor
- papers stay as hover/evidence text, not graph nodes

```bash
python -m src.graph.export_direction_graph \
  --direction "Agent" \
  --keywords "AI Agent,LLM Agent,multi-agent,tool use,planning"
```

![Direction graph demo](docs/assets/demo-direction-graph.svg)

### 2. Search By Professor

Input a professor name and generate a radial ego graph. The professor is fixed in
the center; students are placed on a ring; purple lines mean professor-student
guidance/collaboration; gray lines mean student-student coauthored papers.

```bash
python -m src.graph.export_pi_ego_graph --pi "Xipeng Qiu" --max-students 16
```

![Professor ego graph demo](docs/assets/demo-professor-ego.svg)

## Outputs

Generated artifacts are written under `data/exports/`:

- `direction_graph.html/json/graphml`
- `direction_graph_<direction>.html/json/graphml`
- `pi_ego_graph.html/json`
- `pi_ego_<teacher_name>.html/json`

`data/exports/` is ignored by git so local generated data is not published by
default.

## Installation

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Optional environment variables:

| Variable | Required | Notes |
|---|---:|---|
| `OPENALEX_EMAIL` | recommended | OpenAlex polite-pool email |
| `GITHUB_TOKEN` | recommended | Needed for stronger repo/project signals |
| `SEMANTIC_SCHOLAR_API_KEY` | optional | Higher Semantic Scholar quota |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | optional | Reserved for LLM analysis |

## Build The Local Database

```bash
# Run configured seed labs.
python -m src.pipeline.run_all

# Debug with only a few labs.
python -m src.pipeline.run_all --limit-labs 2

# Run one professor/lab target.
python -m src.pipeline.run_lab \
  --pi "Xipeng Qiu" \
  --school "Fudan University" \
  --keywords "LLM,PEFT,LoRA"
```

The local database is `data/radar.db`. It is ignored by git.

## Dashboard

```bash
streamlit run app.py
```

Dashboard pages include lab radar, student radar, repo radar, focused graphs and
search views.

## Local API

The API is optional. It is a local machine-callable entry point for web pages,
LLM agents or skills. Direct commands work without starting it.

```bash
uvicorn src.api:app --reload
```

Main endpoints:

- `POST /directions/graph/export`
- `POST /professors/{name}/ego/export`

Legacy World Model endpoints are kept for compatibility but are not the primary
workflow.

## Project Structure

```text
src/
  collectors/           public data collection
  entity_resolution/    people, org and paper matching
  classifiers/          keyword and startup-signal classifiers
  scoring/              lab, person and repo scoring
  graph/                graph builders and HTML/JSON/GraphML exports
  services/             reusable functions for API/skill workflows
  pipeline/             orchestration commands
app.py                  Streamlit dashboard
skills/ai-lab-radar/    repository-local skill draft
docs/                   project docs and demo assets
```

## Docs

- [Project map](docs/PROJECT_MAP.md)
- [Generic direction graph](docs/GENERIC_DIRECTION_GRAPH.md)
- [Professor ego graph](docs/PI_EGO_GRAPH.md)
- [Open-source checklist](docs/OPEN_SOURCE_CHECKLIST.md)
- [API and skill plan](docs/API_AND_SKILL_PLAN.md)

## Tests

```bash
pytest -q
```

## Data And Privacy

The project is designed around public data sources, but local outputs may contain
cached public data, inferred relationships and analysis state. Do not publish:

- `.env`
- `data/radar.db`
- `data/exports/`
- `data/raw/`
- `data/processed/`

These are already ignored by `.gitignore`.

## Current Limits

- Without `GITHUB_TOKEN`, engineering/project signals are weaker.
- Student/PI relationships are inferred from public signals and may contain
  noise.
- Direction search is keyword/evidence based; it is meant for scouting, not as a
  ground-truth academic taxonomy.
- No private company-registration or financing database is included.

## Roadmap

- Generalize direction templates and keyword expansion.
- Add richer professor search across the full radar graph.
- Add sanitized demo datasets.
- Add optional LLM-generated memos grounded in stored evidence.
- Package `skills/ai-lab-radar` as an installable Codex/Claude-style skill.

