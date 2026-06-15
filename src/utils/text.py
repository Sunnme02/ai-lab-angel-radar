"""文本工具:名字规范化、标题规范化、摘要还原。"""
import re


def normalize_name(name: str) -> str:
    """姓名规范化:小写、去标点、压空白。用于消歧匹配。"""
    if not name:
        return ""
    s = re.sub(r"[^\w\s]", " ", name.lower())
    return re.sub(r"\s+", " ", s).strip()


def normalize_title(title: str) -> str:
    if not title:
        return ""
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def restore_abstract(inv: dict) -> str:
    """OpenAlex abstract_inverted_index → 正常文本。"""
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))[:3000]
