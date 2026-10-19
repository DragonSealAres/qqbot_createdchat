"""核心事件处理：提问检索、序号选择、三条管理指令。

仅响应群聊中 @ 到机器人本身的消息；纯数字序号回复在存在待选会话时才会响应。
"""

from datetime import datetime
from typing import Any

from nonebot import on_message
from nonebot.adapters.onebot.v11 import (
    Bot,
    Event,
    GroupMessageEvent,
    Message,
    MessageSegment,
)

from .matcher import search
from .session import clear_session, get_session, set_session
from .storage import load_qa, next_id, save_qa

# 指令前缀
CMD_ADD = "添加问题"
CMD_KEYWORD = "关键词添加"
CMD_MANAGE = "问题管理"

# 固定提示语
TIP_NO_MATCH = "暂时没有收录这个问题，请@管理员手动询问。"
TIP_ADD_FORMAT = "格式错误，正确格式：@bot 添加问题 问题 答案。"
TIP_KW_FORMAT = "格式错误，正确格式：@bot 关键词添加 问题 关键词1 关键词2 ..."
TIP_KW_NOT_FOUND = "未找到该问题。"
TIP_SAVE_FAIL = "❌写入知识库失败。"
TIP_SELECT_EXPIRED = "选择过期，请重新提问。"
TIP_SELECT_INVALID = "序号无效，请回复正确的序号。"


# ---------------------------------------------------------------------------
# 规则
# ---------------------------------------------------------------------------

def _rule_at_bot(event: Event) -> bool:
    """仅当群聊消息 @ 到机器人本身时返回 True。"""
    if not isinstance(event, GroupMessageEvent):
        return False
    for seg in event.get_message():
        if seg.type == "at" and str(seg.data.get("qq")) == str(event.self_id):
            return True
    return False


def _rule_select(event: Event) -> bool:
    """仅当群聊消息为纯数字、且该用户存在待选会话时返回 True。"""
    if not isinstance(event, GroupMessageEvent):
        return False
    if not event.get_plaintext().strip().isdigit():
        return False
    return get_session(event.user_id) is not None


# 序号选择处理器：优先级最高，命中即阻断后续
qa_select = on_message(rule=_rule_select, priority=1, block=True)

# 主处理器：负责提问检索与三条指令（@ 机器人触发）
qa_main = on_message(rule=_rule_at_bot, priority=10, block=True)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _build_candidates_text(results: list[tuple[float, dict[str, Any]]]) -> str:
    """拼装候选列表文案。"""
    lines = ["找到相关候选，请回复序号选择："]
    for index, (_, entry) in enumerate(results, 1):
        lines.append(f"【{index}】 {entry.get('question', '')},id:{entry.get('id', '')}")
    return "\n".join(lines)


def _build_manage_text(entry: dict[str, Any]) -> str:
    """拼装问题管理的完整信息文案。"""
    keywords = entry.get("keyword") or []
    kw_text = ",".join(str(k) for k in keywords) if keywords else "无"
    return (
        f"问题名: {entry.get('question', '')}\n"
        f"id: {entry.get('id', '')}\n"
        f"关键词: {kw_text}\n"
        f"回答: {entry.get('text', '')}\n"
        f"时间: {entry.get('time') or '无'}\n"
        f"添加人: {entry.get('qqnum') or '无'}\n"
        f"相关图片: {entry.get('img_url') or '无'}"
    )


# ---------------------------------------------------------------------------
# 序号选择：返回图文答案 / 完整管理信息
# ---------------------------------------------------------------------------

@qa_select.handle()
async def _handle_select(bot: Bot, event: GroupMessageEvent) -> None:
    session = get_session(event.user_id)
    if session is None:
        return  # 理论不可达（规则已过滤），保底判断

    # 上下文超时：清空会话并提示
    if session.expired():
        clear_session(event.user_id)
        await qa_select.finish(TIP_SELECT_EXPIRED)

    index = int(event.get_plaintext().strip())
    if index < 1 or index > len(session.candidates):
        await qa_select.finish(TIP_SELECT_INVALID)

    entry = session.candidates[index - 1]
    clear_session(event.user_id)

    # 问题管理模式：返回完整信息
    if session.mode == "manage":
        await qa_select.finish(_build_manage_text(entry))

    # 问答模式：文字 + 可选图片的混合回复
    msg = Message(entry.get("text", ""))
    img_url = str(entry.get("img_url", "") or "")
    if img_url:
        # 支持网络直链；本地路径仅测试用，可传 file:///绝对路径 或本地路径
        msg += MessageSegment.image(img_url)
    await qa_select.finish(msg)


# ---------------------------------------------------------------------------
# 指令分发（@ 机器人触发）
# ---------------------------------------------------------------------------

@qa_main.handle()
async def _handle_main(bot: Bot, event: GroupMessageEvent) -> None:
    text = event.get_plaintext().strip()
    if text.startswith(CMD_ADD):
        await _handle_add(event, text)
    elif text.startswith(CMD_KEYWORD):
        await _handle_keyword(event, text)
    elif text.startswith(CMD_MANAGE):
        await _handle_manage(event, text)
    else:
        await _handle_question(event, text)


async def _handle_question(event: GroupMessageEvent, text: str) -> None:
    """普通提问：检索并返回候选列表。"""
    results = search(text, load_qa())
    if not results:
        await qa_main.finish(TIP_NO_MATCH)
    # 保存会话上下文，等待用户回复序号
    set_session(event.user_id, [entry for _, entry in results], "answer")
    await qa_main.finish(_build_candidates_text(results))


async def _handle_manage(event: GroupMessageEvent, text: str) -> None:
    """指令 3：问题管理，检索候选后按序号输出完整信息。"""
    query = text[len(CMD_MANAGE):].lstrip()
    results = search(query, load_qa())
    if not results:
        await qa_main.finish(TIP_NO_MATCH)
    set_session(event.user_id, [entry for _, entry in results], "manage")
    await qa_main.finish(_build_candidates_text(results))


async def _handle_add(event: GroupMessageEvent, text: str) -> None:
    """指令 1：添加问题。"""
    body = text[len(CMD_ADD):].lstrip()
    parts = body.split(maxsplit=1)
    # 首个空格前为 question，其后全部为 text（允许含空格）
    if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
        await qa_main.finish(TIP_ADD_FORMAT)

    question, answer = parts[0].strip(), parts[1]
    data = load_qa()
    entry = {
        "id": next_id(data),
        "keyword": [],
        "question": question,
        "text": answer,
        "img_url": "",
        "qqnum": str(event.user_id),
        "time": datetime.now().strftime("%Y.%m.%d"),
    }
    data.append(entry)
    if not save_qa(data):
        await qa_main.finish(TIP_SAVE_FAIL)
    await qa_main.finish(f"✅添加成功，问题:{question}，id:{entry['id']}")


async def _handle_keyword(event: GroupMessageEvent, text: str) -> None:
    """指令 2：关键词添加。"""
    body = text[len(CMD_KEYWORD):].lstrip()
    parts = body.split(maxsplit=1)
    if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
        await qa_main.finish(TIP_KW_FORMAT)

    search_text, new_words_text = parts[0].strip(), parts[1]
    data = load_qa()
    results = search(search_text, data)
    if not results:
        await qa_main.finish(TIP_KW_NOT_FOUND)

    # 取综合得分最高的条目作为目标
    target = results[0][1]
    keywords = target.get("keyword") or []
    if not isinstance(keywords, list):
        keywords = []

    # 追加关键词并去重
    added: list[str] = []
    for word in new_words_text.split():
        if word not in keywords and word not in added:
            added.append(word)
    keywords.extend(added)
    target["keyword"] = keywords

    if not save_qa(data):
        await qa_main.finish(TIP_SAVE_FAIL)
    added_text = " ".join(added) if added else "（无新增，关键词已存在）"
    await qa_main.finish(
        f"✅已经成功为问题【{target.get('question', '')}】,"
        f"id:{target.get('id', '')} 添加关键词：{added_text}"
    )
