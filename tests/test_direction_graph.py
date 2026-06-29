from src.graph.export_direction_graph import find_hits, parse_keywords, slugify


def test_parse_keywords_dedupes_direction_and_keywords():
    assert parse_keywords("Agent", "AI Agent, Agent, tool use") == [
        "Agent",
        "AI Agent",
        "tool use",
    ]


def test_find_hits_matches_hyphenated_phrases():
    hits = find_hits("LLM-agent tool use and planning", ["LLM Agent", "tool use", "AI"])
    assert hits == ["LLM Agent", "tool use"]


def test_slugify_direction_name():
    assert slugify("AI Agent / Tool Use") == "ai_agent_tool_use"

