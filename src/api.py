"""Optional FastAPI entry point for local/hosted graph queries.

Run with:
    uvicorn src.api:app --reload
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from .graph.export_direction_graph import export_direction_graph
from .graph.export_pi_ego_graph import export_pi_ego_graph
from .services.world_model_service import (
    direction_subgraph,
    directions,
    professor_subgraph,
    refresh_graph,
)

app = FastAPI(
    title="AI Lab Angel Radar API",
    version="0.1.0",
    description="Thin API for deterministic lab-radar graph queries.",
)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/world-model/directions")
def list_world_model_directions():
    return {"directions": directions()}


@app.get("/world-model/directions/{direction}")
def get_world_model_direction(direction: str):
    try:
        return direction_subgraph(direction)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/world-model/professors/{name}")
def get_world_model_professor(name: str):
    try:
        return professor_subgraph(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/world-model/export")
def refresh_world_model_graph(
    max_labs_per_track: int = Query(10, ge=1, le=50),
    max_students_per_lab: int = Query(6, ge=0, le=30),
):
    return refresh_graph(
        max_labs_per_track=max_labs_per_track,
        max_students_per_lab=max_students_per_lab,
    )


@app.post("/directions/graph/export")
def refresh_direction_graph(
    direction: str = Query(..., min_length=2),
    keywords: str = "",
    max_labs: int = Query(12, ge=1, le=50),
    max_students_per_lab: int = Query(6, ge=0, le=30),
):
    return export_direction_graph(
        direction,
        keywords,
        max_labs=max_labs,
        max_students_per_lab=max_students_per_lab,
    )


@app.post("/professors/{name}/ego/export")
def refresh_professor_ego_graph(
    name: str,
    max_students: int = Query(16, ge=1, le=40),
):
    try:
        return export_pi_ego_graph(name, max_students=max_students)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
