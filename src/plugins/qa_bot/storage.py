"""知识库 qa.json 的读写封装，统一做异常兜底。"""

import json
from typing import Any

from .config import QA_FILE


def load_qa() -> list[dict[str, Any]]:
    """读取知识库。

    文件不存在、空文件或 JSON 非法时返回空列表，不向上抛异常。
    """
    try:
        with QA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, OSError):
        return []
    # 兼容非列表结构（例如误写成对象）
    if not isinstance(data, list):
        return []
    return data


def save_qa(data: list[dict[str, Any]]) -> bool:
    """写回知识库；成功返回 True，IO 异常返回 False。"""
    try:
        with QA_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def next_id(data: list[dict[str, Any]]) -> int:
    """计算自增 id：现有最大 id + 1（空库从 1 开始）。"""
    max_id = 0
    for entry in data:
        try:
            max_id = max(max_id, int(entry.get("id", 0)))
        except (TypeError, ValueError):
            continue
    return max_id + 1
