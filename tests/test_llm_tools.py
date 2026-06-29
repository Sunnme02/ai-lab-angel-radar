import json

from src.llm.audit_graph import audit_graph
from src.llm.expand_direction import expand_direction
from src.llm.graph_context import rule_audit, summarize_graph
from src.llm.write_memo import write_memo


def sample_graph():
    return {
        "meta": {"pi_name": "Xipeng Qiu"},
        "nodes": [
            {"id": "person:1", "type": "pi", "label": "Xipeng Qiu", "score": 20},
            {"id": "person:2", "type": "student", "label": "Zhiheng Xi", "score": 80},
            {"id": "person:3", "type": "student", "label": "Reviewer Needed", "score": 10},
        ],
        "edges": [
            {
                "source": "person:1",
                "target": "person:2",
                "relation": "ADVISES_AND_COLLABORATES",
                "confidence": 0.95,
                "coauthored_papers": 4,
                "strength": 6,
                "evidence": ["Paper A"],
            },
            {
                "source": "person:1",
                "target": "person:3",
                "relation": "ADVISES_AND_COLLABORATES",
                "confidence": 0.5,
                "coauthored_papers": 0,
                "strength": 1,
            },
        ],
    }


def test_expand_direction_fallback_handles_chinese_world_model():
    data = expand_direction("世界模型", use_llm=False)
    assert "World Model" in data["keywords"]


def test_graph_summary_and_rule_audit():
    data = sample_graph()
    summary = summarize_graph(data)
    audit = rule_audit(data)
    assert summary["node_count"] == 3
    assert audit["high_confidence"][0]["target"] == "Zhiheng Xi"
    assert audit["possible_false_positive"][0]["target"] == "Reviewer Needed"


def test_audit_graph_no_llm_writes_markdown(tmp_path):
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(sample_graph()), encoding="utf-8")
    out = audit_graph(graph_path, use_llm=False)
    assert out.exists()
    assert "图谱审查报告" in out.read_text(encoding="utf-8")


def test_write_memo_no_llm_writes_markdown(tmp_path):
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(sample_graph()), encoding="utf-8")
    out = write_memo(graph_path, use_llm=False)
    assert out.exists()
    assert "图谱简报" in out.read_text(encoding="utf-8")

