"""临时会话上下文：以用户 QQ 为 key 保存候选列表，带 30 秒过期时间。"""

import time
from dataclasses import dataclass
from typing import Any

from .config import SESSION_TIMEOUT


@dataclass
class Session:
    """一次检索产生的待选择上下文。"""

    candidates: list[dict[str, Any]]  # 候选条目（已按综合得分降序）
    mode: str                         # "answer" 返回图文 / "manage" 返回完整信息
    expire_at: float                  # 过期时间戳

    def expired(self) -> bool:
        """是否已过期。"""
        return time.time() > self.expire_at


# 会话存储：{用户 QQ: Session}
_sessions: dict[str, Session] = {}


def set_session(user_id: int | str, candidates: list[dict[str, Any]], mode: str) -> None:
    """写入会话，有效期 SESSION_TIMEOUT 秒。"""
    _sessions[str(user_id)] = Session(candidates, mode, time.time() + SESSION_TIMEOUT)


def get_session(user_id: int | str) -> Session | None:
    """读取会话（不做过期过滤，由调用方判断 expired）。"""
    return _sessions.get(str(user_id))


def clear_session(user_id: int | str) -> None:
    """清空会话。"""
    _sessions.pop(str(user_id), None)
