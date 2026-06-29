# Project Map

This repository is the open-source candidate for the AI lab angel-radar work.
The parent workspace also contains local notes and paper-collection outputs; do
not publish the parent folder as-is.

## Main Entry Points

- `app.py`: Streamlit dashboard.
- `src/api.py`: optional FastAPI entry point for local graph queries.
- `python -m src.pipeline.run_all`: run the full data pipeline from configured seed labs.
- `python -m src.pipeline.run_lab`: run one school/PI/keyword target.
- `python -m src.graph.export_world_model_graph`: export the focused World Model graph.
- `python -m src.graph.export_direction_graph --direction "Agent" --keywords "..."`
  exports a generic AI direction graph.
- `python -m src.graph.export_pi_ego_graph --pi "Fuchun Sun"`: export a
  professor-centered radial ego graph.

## Core Packages

- `src/collectors/`: public data collection from OpenAlex, Semantic Scholar, DBLP,
  OpenReview, web pages and GitHub.
- `src/entity_resolution/`: people, organization and paper matching.
- `src/classifiers/`: direction and startup-signal classifiers.
- `src/scoring/`: lab, person and repo scoring.
- `src/graph/`: graph construction, graph queries and export scripts.
- `src/services/`: reusable deterministic service functions for APIs and agent workflows.
- `src/pipeline/`: orchestration commands.

## Local Data And Generated Outputs

These are intentionally ignored by git:

- `data/radar.db`: local SQLite working database.
- `data/exports/`: generated CSV, JSON, GraphML and HTML outputs.
- `data/raw/` and `data/processed/`: caches/intermediate data.

Seed files that are safe to review and version:

- `data/seeds/labs_seed.yaml`
- `data/seeds/labs_seed_csrankings.yaml`

## Current World Model Output

The current focused graph export is generated at:

- `data/exports/world_model_graph.html`
- `data/exports/world_model_graph.json`
- `data/exports/world_model_graph.graphml`
- `data/exports/direction_graph.html`
- `data/exports/direction_graph.json`
- `data/exports/direction_graph.graphml`
- `data/exports/pi_ego_graph.html`
- `data/exports/pi_ego_graph.json`

The HTML is self-contained enough to share as a static local file.

## Project Skill Draft

- `skills/ai-lab-radar/SKILL.md`: repository-local skill draft. It is not
  installed globally yet; treat it as the version-controlled source for a future
  Codex/Claude-style skill.
