# Generic Direction Graph

This export is the general form of the radar search tool. It accepts any AI
direction name and optional keywords, then produces a focused professor/student
knowledge graph.

## Command

```bash
python -m src.graph.export_direction_graph \
  --direction "Agent" \
  --keywords "AI Agent,LLM Agent,multi-agent,tool use,planning"
```

Outputs:

- `data/exports/direction_graph.html`
- `data/exports/direction_graph.json`
- `data/exports/direction_graph.graphml`
- `data/exports/direction_graph_<direction>.html`
- `data/exports/direction_graph_<direction>.json`
- `data/exports/direction_graph_<direction>.graphml`

## Search Logic

The script searches:

- `labs.lab_name`
- `labs.pi_name`
- `labs.pi_name_cn`
- `labs.keywords`
- `papers.title`
- `papers.keywords_matched`
- `papers.venue`

Papers are used as evidence only. They are not drawn as nodes by default.

## Node Logic

The graph keeps:

- direction node
- professor nodes
- student nodes
- school nodes

It intentionally avoids paper nodes and all-author expansion to prevent
hairballs.

## Edge Logic

- `MATCHES_DIRECTION`: direction -> professor
- `AT_SCHOOL`: school -> professor
- `ADVISES`: professor -> student

Edge hover text stores the evidence that caused the direction match.

## When To Use World Model Export

Use `export_world_model_graph` when you want the curated three-bucket World Model
view. Use `export_direction_graph` when you want any arbitrary AI direction.

