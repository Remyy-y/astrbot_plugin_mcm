# 导入 AstrBot 插件开发所需的核心库
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig

# 导入 RCON 库
# 我们会把它加到 requirements.txt 中
import aiomcrcon

# @register(...) 是一个装饰器，用来告诉 AstrBot 这是一个插件
# 请替换 "your_author" 和 "your_repo_url"
@register("mc_rcon", "Remyy", "一个通过 RCON 管理 MC 服务器的插件", "1.0.0", "https://github.com/Remyy-y/astrbot_plugin_mcm")
class MCRconPlugin(Star):
    
    # __init__ 是插件被加载时运行的第一个函数
    # config: AstrBotConfig 参数是自动注入的，它对应 _conf_schema.json 里的配置
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        # self.config 用来保存插件的配置，方便后续在其他函数中调用
        self.config = config
        logger.info("MC RCON 插件已加载！")

    # @filter.command(...) 注册一个聊天命令
    # 当用户发送 "/mc-command <...>" 或 "/mc <...>" 时，会触发下面的函数
    # alias 是命令的别名
    # * 是一个特殊标记，它告诉 AstrBot
    #    "command" 这个参数，应该包含 /mc-command 之后的所有文本内容
    @filter.command("mc-command", alias={'mc'})
    async def handle_mc_command(self, event: AstrMessageEvent, *, command: str):
        """
        处理 MC RCON 命令。
        用户可以通过 /mc <command> 或 /mc-command <command> 来执行 RCON 指令。
        例如: /mc whitelist add SomePlayer
        """
        
        # 1. 从配置中获取 RCON 服务器信息
        # self.config.get(...) 会尝试读取配置项
        #    如果用户没填，就使用一个默认值（比如 "127.0.0.1"）
        host = self.config.get("host", "127.0.0.1")
        port = self.config.get("port", 25575)
        password = self.config.get("password", "")

        # 检查 RCON 密码是否已配置
        if not password or password == "your_rcon_password":
            logger.warn("RCON 密码未配置！")
            # yield event.plain_result(...) 是发送消息给用户的方法
            yield event.plain_result("错误：RCON 密码未在插件配置中设置！")
            return # 结束函数

        # 2. 尝试连接 RCON 服务器并发送命令
        # 我们使用 try...except... 来捕获可能发生的错误（比如连不上服务器、密码错误等）
        # 这是"健壮的错误处理机制"（来自 plugin-new.md）
        try:
            # logger.info(...) 会在 AstrBot 的后台日志中打印信息，方便调试
            logger.info(f"正在向 {host}:{port} 发送 RCON 命令: {command}")
            
            # 使用 aiomcrcon.Client(...) 连接服务器
            # async with ... as ...: 是 Python 异步编程的一种写法
            #   它能确保连接在使用后被正确关闭
            async with aiomcrcon.Client(host, port, password) as client:
                # await client.send_command(...) 异步发送命令并等待服务器响应
                response = await client.send_command(command)
                
                # 3. 处理并返回服务器的响应
                if response:
                    logger.info(f"RCON 响应: {response}")
                    # 将服务器的响应发送给用户
                    yield event.plain_result(f"服务器响应:\n{response}")
                else:
                    logger.info("RCON 命令已执行，服务器无文本响应。")
                    # 有些命令（比如 /whitelist add）成功后可能没有文本返回
                    yield event.plain_result(f"命令 '{command}' 已成功执行（服务器无文本响应）。")

        except Exception as e:
            # 5. 如果发生错误，捕获并通知用户
            logger.error(f"RCON 命令执行失败: {e}")
            yield event.plain_result(f"RCON 错误:\n{e}")

    # 当插件被卸载或禁用时，这个函数会被调用（可选）
    async def terminate(self):
        logger.info("MC RCON 插件已卸载。")