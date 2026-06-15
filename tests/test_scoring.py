import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.scoring.lab_score import score_lab
from src.scoring.person_score import score_person
from src.scoring.repo_score import score_repo
from src.scoring.score_utils import priority


def test_lab_score_bounds_and_explanations():
    r = score_lab({"keyword_paper_count_3y": 12, "total_stars": 2000, "repo_count": 3,
                   "high_potential_student_count": 5, "industry_signal_count": 2,
                   "has_joint_lab": True, "directions": {"Recommendation", "LLM Systems"},
                   "has_vertical_with_data": True, "pi_has_company": True})
    assert 0 <= r["total_score"] <= 100
    assert r["total_score"] == 100  # 全满
    for d in r["dimensions"].values():
        assert "reason" in d and d["reason"]


def test_lab_score_empty_lab_low():
    r = score_lab({"keyword_paper_count_3y": 0, "total_stars": 0, "repo_count": 0,
                   "high_potential_student_count": 0, "directions": set()})
    assert r["total_score"] < 30


def test_person_score_first_author_drives_paper_ability():
    r = score_person({"first_author_count_3y": 3, "max_repo_stars": 0, "repo_count": 0,
                      "matched_keyword_count": 2, "role": "PhD", "centrality": 0})
    assert r["dimensions"]["paper_ability"]["score"] == 20


def test_repo_score_bounds():
    r = score_repo({"stars": 1500, "forks": 200, "last_commit_at": None,
                    "matched_keywords": ["LoRA / PEFT", "LLM Systems"],
                    "productization_signal_count": 5, "has_vertical_scene": True})
    assert 0 <= r["total_score"] <= 100


def test_priority_thresholds():
    assert priority(85) == "High"
    assert priority(70) == "Medium High"
    assert priority(55) == "Medium"
    assert priority(20) == "Low"
