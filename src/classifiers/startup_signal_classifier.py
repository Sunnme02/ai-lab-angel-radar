"""创业信号分类(规格 8.7):从文本判断产品化/产业/创业信号,带证据。规则法。"""
import re

SIGNAL_PATTERNS = {
    "demo": r"\bdemo\b|live demo|playground|try it",
    "api": r"\bapi\b|rest api|endpoint",
    "docker": r"docker|dockerfile|container",
    "package": r"pip install|pypi|npm install|package",
    "benchmark": r"benchmark|sota|state-of-the-art|leaderboard",
    "users": r"\busers?\b|adopted|in production|deployed",
    "enterprise": r"enterprise|company|industry|commercial",
    "deployment": r"deploy|deployment|serving|on-?device|edge",
    "startup": r"startup|spin-?off|co-?founder|创业|成立公司",
    "company": r"\bcompany\b|公司|inc\.|ltd|co\.,",
    "commercialization": r"commercial|成果转化|商业化|monetiz",
    "collaboration": r"collaborat|joint lab|联合实验室|产业合作|partnership",
    "funding": r"funding|raised|融资|天使轮|种子轮|investment|venture",
    "incubator": r"incubator|accelerator|孵化|奇绩|yc\b",
    "patent": r"patent|专利",
    "huggingface": r"huggingface|hf\.co|hugging face|model card|space",
}
COMPILED = {s: re.compile(p, re.I) for s, p in SIGNAL_PATTERNS.items()}


def detect_signals(text: str, evidence_url: str = ""):
    """返回 [{signal_type, confidence, evidence_text, evidence_url}]。"""
    if not text:
        return []
    out = []
    for sig, pat in COMPILED.items():
        m = pat.search(text)
        if m:
            start = max(0, m.start() - 40)
            snippet = text[start:m.end() + 40].replace("\n", " ").strip()
            # 强信号给高置信,弱(单纯关键词)给中
            conf = 0.8 if sig in ("startup", "company", "funding", "incubator",
                                  "commercialization", "patent", "collaboration") else 0.6
            out.append({"signal_type": sig, "confidence": conf,
                        "evidence_text": snippet[:160], "evidence_url": evidence_url})
    return out
