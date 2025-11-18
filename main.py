from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import aiomcrcon

@register("mc_rcon", "Remyy", "一个通过 RCON 管理 MC 服务器的插件", "1.0.1", "https://github.com/Remyy-y/astrbot_plugin_mcm")
class MCRconPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        logger.info("MC RCON 插件已加载！")

    # 【修改】去掉了 *args，避免触发框架报错
    @filter.command("mc-command", alias={'mc'})
    async def handle_mc_command(self, event: AstrMessageEvent):
        host = self.config.get("host", "127.0.0.1")
        port = self.config.get("port", 25575)
        password = self.config.get("password", "")

        # 【修改】手动解析参数
        # event.message_str 是用户的完整消息，比如 "mc forge tps" 或 "/mc list"
        raw_message = event.message_str.strip()
        
        # 我们按空格切割一次
        # parts[0] 是指令头（如 "mc"），parts[1] 是剩下的所有内容（如 "forge tps"）
        parts = raw_message.split(maxsplit=1)
        
        if len(parts) < 2:
            yield event.plain_result("请输入具体的指令，例如：/mc list")
            return
            
        command = parts[1] # 这就是我们要发送给服务器的完整指令

        if not password:
            yield event.plain_result("错误：RCON 密码未配置！")
            return

        try:
            logger.info(f"正在向 {host}:{port} 发送 RCON 命令: {command}")
            
            client = aiomcrcon.Client(host, port, password)
            await client.connect()
            
            # 发送命令
            response = await client.send_cmd(command)
            
            await client.close()
            
            # 处理返回值
            if isinstance(response, tuple):
                response_text = response[0]
            else:
                response_text = response

            if response_text:
                yield event.plain_result(f"服务器响应:\n{response_text}")
            else:
                yield event.plain_result(f"命令 '{command}' 已执行（服务器无文本响应）。")

        except Exception as e:
            logger.error(f"RCON 错误: {e}")
            try:
                await client.close()
            except:
                pass
            yield event.plain_result(f"RCON 执行出错: {e}")