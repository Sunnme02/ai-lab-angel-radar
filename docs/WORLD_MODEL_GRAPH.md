# World Model Graph

This graph is a focused direction map, not the full author-paper graph.

## Goal

Show who is relevant to the World Model direction, with enough context to inspect
professor/student relationships without creating a hairball.

## Direction Buckets

The export script maps papers and labs into three buckets:

- Core World Models: direct World Model / World Modeling / World Simulator /
  latent dynamics / model-based RL language.
- Embodied / Robot World Models: VLA, robot manipulation, embodied agents,
  sim2real, interactive/video world model signals.
- Driving / 4D Scene Models: autonomous driving, occupancy prediction, 4D
  driving scenes, trajectory/planning/closed-loop driving.

The patterns live in `src/graph/export_world_model_graph.py`.

## Export Logic

Papers are used only as direction evidence. They do not become graph nodes.

The graph keeps only:

- direction nodes
- school nodes
- professor nodes
- student nodes

Edges are limited to:

- `HAS_TRACK`: World Model -> direction bucket
- `MATCHES_DIRECTION`: direction bucket -> professor
- `AT_SCHOOL`: school -> professor
- `ADVISES`: professor -> student

For each bucket, the script selects top matching labs and expands up to six
high-confidence students per professor. Professors are never downgraded to
student nodes even if noisy relationship data points at them.

## Regenerate

```bash
python -m src.graph.export_world_model_graph
```

Optional limits:

```bash
python -m src.graph.export_world_model_graph --max-labs-per-track 10 --max-students-per-lab 6
```

Outputs:

- `data/exports/world_model_graph.html`
- `data/exports/world_model_graph.json`
- `data/exports/world_model_graph.graphml`

