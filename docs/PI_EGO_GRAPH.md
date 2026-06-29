# Professor Ego Star Graph

This view is for inspecting one professor at a time.

## Visual Logic

- Professor is fixed in the center.
- Students are placed on a deterministic ring.
- Professor-student edge width reflects advising confidence plus coauthored
  paper evidence.
- Student-student edges appear only when selected students share papers.
- Student color reflects `student_startup_score`.

This is intentionally different from the force-directed overview graph. It is
more stable and easier to compare across professors.

## Regenerate

```bash
python -m src.graph.export_pi_ego_graph --pi "Fuchun Sun" --max-students 16
```

Outputs:

- `data/exports/pi_ego_graph.html`
- `data/exports/pi_ego_graph.json`
- `data/exports/pi_ego_<teacher_name>.html`
- `data/exports/pi_ego_<teacher_name>.json`

## Interpretation

Use thick professor-student lines as "stronger collaboration/advising" signals,
not absolute facts. Relationship data is inferred from public sources and can be
noisy. Hovering lines in the HTML shows coauthored-paper evidence when present.

