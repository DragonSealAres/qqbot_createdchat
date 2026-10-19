"""NoneBot2 入口：注册 OneBot v11 适配器并加载插件。

Lagrange.OneBot 侧以反向 WebSocket 连接本机：
    ws://127.0.0.1:8080/onebot/v11/ws
"""

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter


def main() -> None:
    # 初始化 NoneBot，读取 .env 配置
    nonebot.init()
    driver = nonebot.get_driver()
    # 注册 OneBot v11 适配器
    driver.register_adapter(OneBotV11Adapter)
    # 读取 pyproject.toml 中的 [tool.nonebot]，自动加载 src/plugins 下的插件
    nonebot.load_from_toml("pyproject.toml")
    nonebot.run()


if __name__ == "__main__":
    main()
