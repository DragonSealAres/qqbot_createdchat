"""混合打分检索：fuzzy 模糊相似度 + 关键词命中，两项各占一半权重。"""

import re
from typing import Any

from fuzzywuzzy import fuzz

from .config import SCORE_THRESHOLD, TOP_K

# 仅保留中文、英文、数字，其余（标点 / 表情 / 特殊符号 / 空白）全部剔除
_CLEAN_RE = re.compile(r"[^\u4e00-\u9fa5a-zA-Z0-9]")


def preprocess(text: str) -> str:
    """清洗文本：去除标点、表情、特殊符号，只保留中英文数字。"""
    if not text:
        return ""
    return _CLEAN_RE.sub("", str(text))


def fuzzy_score(query: str, question: str) -> float:
    """fuzzy 分数：用户提问 VS 标准问题 的 partial_ratio，范围 0~100。"""
    if not query or not question:
        return 0.0
    return float(fuzz.partial_ratio(query, question))


def keyword_score(query: str, keywords: list[Any] | None) -> float:
    """关键词分数：命中 keyword 数组内任意词得 100，否则得 0。"""
    if not keywords:
        return 0.0
    for word in keywords:
        cleaned = preprocess(word)
        if cleaned and cleaned in query:
            return 100.0
    return 0.0


def score_entry(query: str, entry: dict[str, Any]) -> float:
    """单条综合得分 = (fuzzy_score + keyword_score) / 2。

    注意：query 与 question 均需已预处理（调用方在 search 中统一清洗）。
    """
    fuzzy = fuzzy_score(query, preprocess(entry.get("question", "")))
    keyword = keyword_score(query, entry.get("keyword") or [])
    return (fuzzy + keyword) / 2


def search(
    query: str, data: list[dict[str, Any]]
) -> list[tuple[float, dict[str, Any]]]:
    """检索知识库。

    返回按综合得分降序排列的候选列表，仅保留总分 >= 阈值的前 TOP_K 条。
    """
    cleaned = preprocess(query)
    hits: list[tuple[float, dict[str, Any]]] = []
    for entry in data:
        total = score_entry(cleaned, entry)
        if total >= SCORE_THRESHOLD:
            hits.append((total, entry))
    hits.sort(key=lambda item: item[0], reverse=True)
    return hits[:TOP_K]
