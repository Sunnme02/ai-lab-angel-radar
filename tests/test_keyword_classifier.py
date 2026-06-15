import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.classifiers.keyword_classifier import classify_text, match_focus_keywords
from src.classifiers.startup_signal_classifier import detect_signals


def test_classify_text_tags():
    tags = classify_text("Efficient LoRA fine-tuning for LLM inference acceleration")
    assert "LoRA / PEFT" in tags
    assert "Inference Optimization" in tags


def test_classify_embodied():
    assert "Embodied AI" in classify_text("A world model for robot manipulation")


def test_match_focus_keywords():
    mk = match_focus_keywords("We propose an AI Agent with LoRA", ["AI Agent", "LoRA", "Recommendation"])
    assert set(mk) == {"AI Agent", "LoRA"}


def test_startup_signals_with_evidence():
    sigs = detect_signals("This startup raised seed funding; pip install demo; Docker support",
                          "http://x")
    types = {s["signal_type"] for s in sigs}
    assert "startup" in types and "funding" in types and "docker" in types
    for s in sigs:
        assert s["evidence_text"] and 0 < s["confidence"] <= 1
