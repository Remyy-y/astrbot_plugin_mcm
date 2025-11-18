from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig

# 导入 aio-mc-rcon 库 (虽然包名叫 aio-mc-rcon，但导入名是 aiomcrcon)
import aiomcrcon

@register("mc_rcon", "Remyy", "一个通过 RCON 管理 MC 服务器的插件", "1.0.1", "https://github.com/Remyy-y/astrbot_plugin_mcm")
class MCRconPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        logger.info("MC RCON 插件已加载！")

    # 注意这里：改成了 *args，这样就能接收 "forge", "tps" 等多个部分了
    @filter.command("mc-command", alias={'mc'})
    async def handle_mc_command(self, event: AstrMessageEvent, *args):
        host = self.config.get("host", "127.0.0.1")
        port = self.config.get("port", 25575)
        password = self.config.get("password", "")

        # 将参数重新拼接成一个字符串，中间用空格隔开
        # 比如用户发 /mc forge tps，args 就是 ('forge', 'tps')
        # 拼接后变成 "forge tps"
        command = " ".join(args)

        if not command:
            yield event.plain_result("请输入要执行的命令，例如：/mc list")
            return

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
            
            # 【新功能】处理返回值
            # 有时候库会返回 ('结果文本', 12345) 这样的元组
            # 我们只需要第一部分
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