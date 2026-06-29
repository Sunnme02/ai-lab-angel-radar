"""Expand a natural-language AI direction into graph-search keywords."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .client import LLMClient, LLMConfig, extract_json
from .prompts import DIRECTION_EXPAND_SYSTEM, DIRECTION_EXPAND_USER


FALLBACK_KEYWORDS = {
    "world model": [
        "World Model",
        "World Modeling",
        "World Simulator",
        "latent dynamics",
        "model-based RL",
        "interactive video generation",
        "driving world model",
        "occupancy prediction",
    ],
    "agent": [
        "AI Agent",
        "LLM Agent",
        "multi-agent",
        "tool use",
        "planning",
        "reasoning",
        "workflow automation",
        "autonomous agent",
    ],
    "embodied": [
        "embodied agent",
        "robot manipulation",
        "VLA",
        "vision-language-action",
        "sim2real",
        "robot learning",
    ],
}

FALLBACK_ALIASES = {
    "世界模型": "world model",
    "智能体": "agent",
    "代理": "agent",
    "具身": "embodied",
    "机器人": "embodied",
}


def fallback_expand(direction: str) -> dict:
    lowered = direction.lower()
    keywords = [direction]
    for key, values in FALLBACK_KEYWORDS.items():
        if key in lowered or any(part in lowered for part in key.split()):
            keywords.extend(values)
    for alias, key in FALLBACK_ALIASES.items():
        if alias in direction and key in FALLBACK_KEYWORDS:
            keywords.extend(FALLBACK_KEYWORDS[key])
    seen = []
    for item in keywords:
        if item and item.lower() not in {x.lower() for x in seen}:
            seen.append(item)
    return {
        "direction": direction,
        "keywords": seen,
        "exclude_keywords": [],
        "notes": "未调用 LLM；使用内置关键词模板生成，可手动补充。",
    }


def expand_direction(
    direction: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    use_llm: bool = True,
) -> dict:
    client = LLMClient(LLMConfig.from_env(provider=provider, model=model))
    if not use_llm or not client.available:
        return fallback_expand(direction)
    response = client.complete(
        DIRECTION_EXPAND_SYSTEM,
        DIRECTION_EXPAND_USER.format(direction=direction),
    )
    return extract_json(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--direction", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--provider", default=None, choices=["openai", "anthropic"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()

    data = expand_direction(
        args.direction,
        provider=args.provider,
        model=args.model,
        use_llm=not args.no_llm,
    )
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
