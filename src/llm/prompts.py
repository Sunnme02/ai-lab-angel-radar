"""Prompt templates for optional LLM review commands."""

DIRECTION_EXPAND_SYSTEM = """You expand AI research directions for a graph search tool.
Return only valid JSON. Do not invent facts, labs, or people."""

DIRECTION_EXPAND_USER = """Expand this AI direction into search terms.

Direction: {direction}

Return JSON with:
- direction: concise English title
- keywords: 8-18 precise search keywords or phrases
- exclude_keywords: 0-8 terms that would make matches too broad
- notes: one short Chinese note explaining the search boundary
"""

GRAPH_AUDIT_SYSTEM = """You audit an AI lab relationship graph.
Use only the supplied JSON summary. Do not claim official advisor/student facts.
Write concise Chinese. Distinguish strong inferred evidence from items needing
manual review."""

GRAPH_AUDIT_USER = """Audit this graph summary.

{summary_json}

Write a Chinese markdown report with:
1. overall risk level
2. high-confidence relationships
3. relationships needing manual review
4. possible false positives
5. suggested next checks
"""

MEMO_SYSTEM = """You write concise Chinese research scouting memos from graph data.
Use only supplied evidence. Avoid hype and avoid unsupported claims."""

MEMO_USER = """Write a Chinese memo from this graph summary.

{summary_json}

Cover:
- graph scope
- key professors or nodes
- student/coauthor signals
- why this direction may be worth follow-up
- caveats and next steps
"""

