from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import aiomcrcon
import asyncio # 引入 asyncio 用于延时

@register("mc_rcon", "Remyy", "一个通过 RCON 管理 MC 服务器的插件", "1.2.0", "https://github.com/Remyy-y/astrbot_plugin_mcm")
class MCRconPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        logger.info("MC RCON 插件已加载！")

    @filter.command("mc-command", alias={'mc'})
    async def handle_mc_command(self, event: AstrMessageEvent):
        host = self.config.get("host", "127.0.0.1")
        port = self.config.get("port", 25575)
        password = self.config.get("password", "")

        raw_message = event.message_str.strip()
        parts = raw_message.split(maxsplit=1)
        
        if len(parts) < 2:
            yield event.plain_result("请输入具体的指令，例如：/mc list")
            return
            
        user_command = parts[1].strip() # 用户输入的指令
        actual_command = user_command   # 实际发送给 RCON 的指令
        is_restart = False

        # --- 快捷指令映射 ---
        # 1. 在线人数查询
        if user_command in ["在线", "online", "list"]:
            actual_command = "list"
        
        # 2. 重启指令 (重启 = 发送 stop + 外部脚本循环)
        elif user_command in ["重启", "restart"]:
            is_restart = True
            actual_command = "stop"
            yield event.plain_result("收到重启指令，正在进行10秒倒计时并广播...")
        
        # ------------------

        if not password:
            yield event.plain_result("错误：RCON 密码未配置！")
            return

        client = None
        try:
            logger.info(f"正在向 {host}:{port} 发送 RCON 命令: {actual_command}")
            
            client = aiomcrcon.Client(host, port, password)
            await client.connect()
            
            # 如果是重启，执行倒计时广播逻辑
            if is_restart:
                # 倒计时 10 秒
                await client.send_cmd("say §cServer is restarting in 10 seconds...")
                await asyncio.sleep(5)
                
                await client.send_cmd("say §cServer is restarting in 5 seconds...")
                await asyncio.sleep(2)
                
                await client.send_cmd("say §c3...")
                await asyncio.sleep(1)
                
                await client.send_cmd("say §c2...")
                await asyncio.sleep(1)
                
                await client.send_cmd("say §c1...")
                await asyncio.sleep(1)
                
                # 保存数据
                await client.send_cmd("save-all")
                await asyncio.sleep(1) 

            # 发送实际命令 (list, stop, 或其他原版指令)
            response = await client.send_cmd(actual_command)
            
            await client.close()
            
            # 处理返回值
            if isinstance(response, tuple):
                response_text = response[0]
            else:
                response_text = response

            if response_text:
                # 为了防止 list 显示太长，可以简单处理一下，这里直接返回
                yield event.plain_result(f"服务器响应:\n{response_text}")
            else:
                # 如果是 stop 指令，通常没有响应或连接直接断开
                if is_restart or actual_command == "stop":
                    yield event.plain_result(f"指令 '{actual_command}' 已发送，服务器正在关闭/重启。")
                else:
                    yield event.plain_result(f"命令 '{actual_command}' 已执行（服务器无文本响应）。")

        except Exception as e:
            # 如果发送 stop 后服务器立刻关闭，可能会导致连接重置错误，这是正常的
            if (is_restart or actual_command == "stop") and ("Connection reset" in str(e) or "closed" in str(e)):
                yield event.plain_result("指令已发送，服务器连接已断开（这是正常的重启现象）。")
            else:
                logger.error(f"RCON 错误: {e}")
                yield event.plain_result(f"RCON 执行出错: {e}")
            
            if client:
                try:
                    await client.close()
                except:
                    pass