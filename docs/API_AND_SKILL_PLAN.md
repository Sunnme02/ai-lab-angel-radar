# API And Skill Plan

The next product step is to turn the current pipeline into an LLM-guided research
tool. The LLM should choose or refine a direction, then call deterministic local
steps for collection, scoring and graph export.

## Current Thin API

The first local API entry point is `src/api.py`.

Run it with:

```bash
uvicorn src.api:app --reload
```

Available endpoints:

- `GET /health`
- `GET /world-model/directions`
- `GET /world-model/directions/{direction}`
- `GET /world-model/professors/{name}`
- `POST /world-model/export`
- `POST /directions/graph/export`
- `POST /professors/{name}/ego/export`

The API is intentionally thin. World Model endpoints call
`src/services/world_model_service.py`; the generic direction endpoint calls
`src.graph.export_direction_graph`.

## Next API Shape

Add broader endpoints after the generic direction graph is stable:

- `POST /directions/search`: richer arbitrary direction search beyond graph export.
- `POST /professors/search`: professor/school query across the full radar graph.
- `GET /exports/{name}`: return generated HTML/JSON/GraphML artifacts.

## LLM Role

The LLM should not be the source of truth. It should:

- translate a user's fuzzy direction into keyword buckets
- explain why a lab/person was included
- draft memos from stored evidence
- propose follow-up search keywords

The database, scoring functions and graph exporter remain deterministic.

## Skill Candidate

The repository now includes a draft skill at:

- `skills/ai-lab-radar/SKILL.md`

It can later be installed as a real Codex/Claude-style skill. The skill should
wrap this workflow:

1. Ask for a target direction or professor.
2. Run the relevant local command.
3. Inspect generated JSON.
4. Produce a concise direction map, watchlist and next-step checklist.
5. Link the generated HTML graph.

Possible skill name:

- `ai-lab-radar`

Initial skill commands:

- `build_direction_graph(direction_name, keywords)`
- `inspect_professor(pi_name, school)`
- `summarize_watchlist(export_json)`
