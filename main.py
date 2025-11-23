from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp
import aiomcrcon
import asyncio # 引入 asyncio 用于延时
import time

@register("mc_rcon", "Remyy", "一个通过 RCON 管理 MC 服务器的插件", "1.3.0", "https://github.com/Remyy-y/astrbot_plugin_mcm")
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
            
        user_command = parts[1].strip() 
        actual_command = user_command   
        is_restart = False

        # --- 快捷指令映射 ---
        if user_command in ["在线", "online", "list"]:
            actual_command = "list"
        
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
                for i in [10, 5, 4, 3, 2, 1]:
                    if i == 10 or i <= 5:
                        await client.send_cmd(f"say §cServer restarting in {i}s...")
                        await asyncio.sleep(1 if i <= 5 else 5)
                
                await client.send_cmd("save-all")
                await asyncio.sleep(1) 

            # 发送实际命令
            response = await client.send_cmd(actual_command)
            await client.close()
            
            # 如果是重启指令，启动后台检测任务
            if is_restart:
                yield event.plain_result("服务器正在重启，请稍候... (Bot将自动检测上线状态)")
                # 创建后台任务检测上线，不阻塞当前消息处理
                asyncio.create_task(self.check_server_startup(event, host, port, password))
            else:
                # 普通指令处理
                if isinstance(response, tuple):
                    response_text = response[0]
                else:
                    response_text = response

                if response_text:
                    yield event.plain_result(f"服务器响应:\n{response_text}")
                else:
                    yield event.plain_result(f"命令 '{actual_command}' 已执行。")

        except Exception as e:
            # 忽略重启时的连接断开错误
            if (is_restart or actual_command == "stop") and ("Connection reset" in str(e) or "closed" in str(e)):
                # 虽然报错了，但极有可能是因为服务器关闭了连接，所以也启动检测
                if is_restart:
                    asyncio.create_task(self.check_server_startup(event, host, port, password))
                yield event.plain_result("指令已发送，服务器连接已断开（正在重启中）。")
            else:
                logger.error(f"RCON 错误: {e}")
                yield event.plain_result(f"RCON 执行出错: {e}")
            
            if client:
                try:
                    await client.close()
                except:
                    pass

    async def check_server_startup(self, event: AstrMessageEvent, host, port, password):
        """后台任务：轮询 RCON 直到连接成功，模拟 'Done' 监听"""
        logger.info("开始检测服务器启动状态...")
        
        # 给服务器一点时间完全关闭 (避免连上旧的进程)
        await asyncio.sleep(15) 
        
        start_wait_time = time.time()
        max_retries = 60 # 最多尝试 60 次
        retry_interval = 5 # 每次间隔 5 秒
        # 总共等待 5分钟

        for i in range(max_retries):
            client = None
            try:
                # 尝试连接
                client = aiomcrcon.Client(host, port, password)
                await client.connect()
                
                # 如果能连上，说明 Done 了！
                await client.close()
                
                elapsed = int(time.time() - start_wait_time)
                logger.info(f"服务器重启检测成功，耗时 {elapsed}s")
                
                # 发送群消息通知
                chain = [
                    Comp.Plain(f"✅ 服务器重启成功！\n"),
                    Comp.Plain(f"⏱️ 启动耗时: 约 {elapsed} 秒\n"),
                    Comp.Plain(f"可以在线了！")
                ]
                await self.context.send_message(event.unified_msg_origin, chain)
                return

            except Exception:
                # 连接失败，说明还没启动好
                if i % 2 == 0: # 减少日志刷屏
                    logger.debug(f"服务器尚未启动，{retry_interval}秒后重试...")
                
                if client:
                    try:
                        await client.close()
                    except:
                        pass
                
                await asyncio.sleep(retry_interval)
        
        # 超时处理
        await self.context.send_message(event.unified_msg_origin, Comp.Plain("⚠️ 服务器重启检测超时（5分钟），请检查后台状态。"))