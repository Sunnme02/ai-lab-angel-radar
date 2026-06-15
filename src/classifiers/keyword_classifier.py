"""关键词分类(规格 8.7):根据 title/abstract/readme/homepage 文本判方向标签。规则法。"""
import re

# 标签 → 触发正则(小写)
TAG_PATTERNS = {
    "LoRA / PEFT": r"\blora\b|\bpeft\b|qlora|low-?rank adaptation|parameter-?efficient",
    "LLM Systems": r"llm system|inference engine|serving|kv ?cache|vllm|throughput|long context",
    "Agent": r"\bagent\b|agentic|tool[- ]?use|multi-?agent|workflow",
    "Multimodal": r"multimodal|multi-?modal|vision-?language|\bvlm\b|\bmllm\b|image-?text",
    "AI Infra": r"\bai infra|infrastructure|distributed training|training system|gpu cluster|moe training",
    "Model Compression": r"compression|pruning|quantization|distillation|sparse",
    "Inference Optimization": r"inference (optimization|acceleration|speedup)|speculative decoding|kv ?cache",
    "Recommendation": r"recommend|recsys|ctr|ranking|click-?through",
    "Embodied AI": r"embodied|robot|manipulation|vla\b|world model|locomotion",
    "AI for Finance": r"finance|trading|quant|financial|risk",
    "AI for Healthcare": r"medical|clinical|healthcare|drug|protein|bio",
    "AI for Education": r"education|tutor|learning analytics",
    "AI Security": r"adversarial|jailbreak|backdoor|privacy|watermark|safety|security",
    "Data / Evaluation": r"benchmark|dataset|evaluation|eval\b|leaderboard",
}
COMPILED = {tag: re.compile(p, re.I) for tag, p in TAG_PATTERNS.items()}


def classify_text(text: str):
    """返回命中的方向标签列表(按文本出现)。"""
    if not text:
        return []
    return [tag for tag, pat in COMPILED.items() if pat.search(text)]


def match_focus_keywords(text: str, focus_keywords):
    """返回 text 命中的 focus 关键词(配置里的方向词)。"""
    if not text:
        return []
    low = text.lower()
    return [k for k in focus_keywords if k.lower() in low]
