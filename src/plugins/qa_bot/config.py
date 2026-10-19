"""全局配置：知识库路径与算法阈值。"""

from pathlib import Path

# 知识库文件路径（项目根目录下的 qa.json）
# 当前文件位于 <root>/src/plugins/qa_bot/config.py，parents[3] 即项目根目录
QA_FILE: Path = Path(__file__).resolve().parents[3] / "qa.json"

# 混合打分筛选阈值：总分 >= 该值才计入候选列表
SCORE_THRESHOLD: int = 60

# 候选列表最多返回条数，防止消息刷屏
TOP_K: int = 3

# 会话选择有效期（秒），超时自动清空
SESSION_TIMEOUT: int = 30
