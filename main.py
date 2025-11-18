from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig

# 导入 aio-mc-rcon 库 (虽然包名叫 aio-mc-rcon，但导入名是 aiomcrcon)
import aiomcrcon

@register("mc_rcon", "Remyy", "一个通过 RCON 管理 MC 服务器的插件", "1.0.0", "https://github.com/Remyy-y/astrbot_plugin_mcm")
class MCRconPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        logger.info("MC RCON 插件已加载！")

    @filter.command("mc-command", alias={'mc'})
    async def handle_mc_command(self, event: AstrMessageEvent, *, command: str):
        host = self.config.get("host", "127.0.0.1")
        port = self.config.get("port", 25575)
        password = self.config.get("password", "")

        if not password:
            yield event.plain_result("错误：RCON 密码未配置！")
            return

        try:
            logger.info(f"正在向 {host}:{port} 发送 RCON 命令: {command}")
            
            # 创建客户端实例
            client = aiomcrcon.Client(host, port, password)
            
            # 1. 建立连接
            await client.connect()
            
            # 2. 发送命令 (注意：这个库的方法名是 send_cmd，不是 send_command)
            response = await client.send_cmd(command)
            
            # 3. 关闭连接
            await client.close()
            
            if response:
                yield event.plain_result(f"服务器响应:\n{response}")
            else:
                yield event.plain_result(f"命令 '{command}' 已执行（服务器无文本响应）。")

        except Exception as e:
            logger.error(f"RCON 错误: {e}")
            # 尝试在报错时也关闭连接，防止资源泄露
            try:
                await client.close()
            except:
                pass
            yield event.plain_result(f"RCON 执行出错: {e}")