---
name: ai-lab-radar
description: General AI direction radar skill: given any AI direction, keywords, or professor name, use the local ai-lab-angel-radar project to retrieve lab/professor/student/project signals, build explainable relationship graphs, and summarize startup-relevant watchlists.
---

# AI Lab Radar

Use this skill inside the `ai-lab-angel-radar` repository. It should not be
World-Model-only. It should work for any AI direction, such as Agent, World
Model, Multimodal, Embodied AI, AI Infra, recommendation, model compression or
autonomous driving.

## Core Workflow

1. Identify the user target:
   - direction query, such as Agent, World Model, embodied AI, robotics or autonomous driving
   - professor query, such as a PI name and optional school
   - export query, such as regenerating a direction graph or professor ego graph
2. Prefer deterministic local code over free-form reasoning.
3. Use generated JSON as the source of truth.
4. Explain inclusion using stored evidence, scores and graph edges.
5. Link the HTML export when a visual graph exists.

## General Direction Workflow

1. Preserve the user's original direction name.
2. Expand it into a small keyword set when useful. For example, Agent can map to
   AI Agent, LLM Agent, multi-agent, tool use and planning.
3. Query local lab keywords and paper title/keyword evidence first.
4. Select relevant labs/professors, then expand only high-confidence students.
5. Keep papers as evidence by default. Do not expand every paper author into the
   graph unless the user explicitly asks for an author graph.
6. Return the graph artifact and a concise watchlist.

## Useful Commands

Generate a generic AI direction graph:

```bash
python -m src.graph.export_direction_graph --direction "Agent" --keywords "AI Agent,LLM Agent,multi-agent,tool use,planning"
```

Generate a professor-centered ego star graph:

```bash
python -m src.graph.export_pi_ego_graph --pi "Fuchun Sun" --max-students 16
```

Run the dashboard:

```bash
streamlit run app.py
```

Run the optional local API. The local API is a machine-callable entry point for
web pages, LLM agents or skills; direct commands work without starting it.

```bash
uvicorn src.api:app --reload
```

Run tests:

```bash
pytest -q
```

## API Workflow

Use these endpoints when the API server is running:

- `POST /directions/graph/export`
- `POST /professors/{name}/ego/export`

Legacy World Model endpoints still exist, but they are compatibility endpoints,
not the main skill path:

- `GET /world-model/directions`
- `GET /world-model/directions/{direction}`
- `GET /world-model/professors/{name}`
- `POST /world-model/export`

Legacy World Model aliases include:

- `core`, `world-model`, `world model`
- `embodied`, `robot`, `robotics`, `具身`, `机器人`
- `driving`, `autonomous-driving`, `4d`, `自动驾驶`

## Output Style

For direction queries, return:

- the direction name and keyword set
- the matched direction bucket when a fixed bucket exists
- top professors
- student branches
- evidence titles or direction signals
- the local HTML/JSON export path

For professor queries, return:

- professor node
- school
- matched directions
- student branch
- caveats about noisy inferred relationships

## Safety

Never expose `.env`, tokens, `data/radar.db`, or unpublished raw/cache files.
Treat graph outputs as derived local artifacts unless the user explicitly says
they are ready to publish them.
