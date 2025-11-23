from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import aiomcrcon
import asyncio 
import time

@register("mc_rcon", "Remyy", "一个通过 RCON 管理 MC 服务器的插件", "1.4.0", "https://github.com/Remyy-y/astrbot_plugin_mcm")
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
        # ------------------

        if not password:
            yield event.plain_result("错误：RCON 密码未配置！")
            return

        client = None
        try:
            # 1. 连接 RCON
            client = aiomcrcon.Client(host, port, password)
            await client.connect()
            
            # 2. 如果是重启，先执行关闭流程
            if is_restart:
                logger.info(f"执行重启流程: {host}:{port}")
                
                # 为了节省时间，防止超过QQ回复超时限制，我们缩短倒计时
                # 如果需要更长的倒计时，请自行增加，但风险是QQ可能会报超时
                await client.send_cmd("say §cServer is restarting in 3 seconds...")
                await asyncio.sleep(1)
                await client.send_cmd("say §c2...")
                await asyncio.sleep(1)
                await client.send_cmd("say §c1...")
                await asyncio.sleep(1)
                
                await client.send_cmd("save-all")
                await client.send_cmd("stop") # 发送关闭指令
                
                await client.close() # 这里的连接肯定会断开
                client = None

                # 发送第一条消息，告诉用户正在处理
                # 这一步非常重要，防止平台认为机器人无响应
                yield event.plain_result("⏳ 指令已发送，正在等待服务器重启...\n(Bot 将保持此会话并在启动完成后通知您)")

                # 3. 进入【阻塞式】轮询检测
                # 我们直接在这里死循环等待，直到成功，而不是创建后台任务
                # 这样我们就可以继续使用 yield event.plain_result 给用户发消息了
                
                # 先等待 15 秒让旧进程彻底关闭
                await asyncio.sleep(15)

                start_wait_time = time.time()
                max_retries = 60 # 最多等待 5 分钟
                
                for i in range(max_retries):
                    # 检查是否超时 (QQ 官方机器人通常有被动消息回复时限，约 2-5 分钟)
                    if time.time() - start_wait_time > 280:
                        yield event.plain_result("⚠️ 等待超时：服务器启动时间过长，请手动检查。")
                        return

                    check_client = None
                    try:
                        # 尝试连接
                        check_client = aiomcrcon.Client(host, port, password)
                        await check_client.connect()
                        # 能连上，说明 Done 了
                        await check_client.close()
                        
                        elapsed = int(time.time() - start_wait_time)
                        logger.info(f"重启检测成功，耗时 {elapsed}s")
                        
                        # 【关键】这里使用 yield，复用当前的回复通道
                        yield event.plain_result(f"✅ 服务器重启成功！\n⏱️ 耗时约 {elapsed} 秒，可以在线了！")
                        return # 结束函数
                        
                    except Exception:
                        # 连接失败，继续等待
                        if i % 4 == 0: # 减少日志
                            logger.info("等待服务器启动中...")
                        if check_client:
                            try:
                                await check_client.close()
                            except:
                                pass
                        await asyncio.sleep(5)
                
                yield event.plain_result("⚠️ 检测循环结束，服务器似乎未能正常启动。")
                return

            else:
                # --- 普通指令处理逻辑 (非重启) ---
                response = await client.send_cmd(actual_command)
                await client.close()
                
                if isinstance(response, tuple):
                    response_text = response[0]
                else:
                    response_text = response

                if response_text:
                    yield event.plain_result(f"服务器响应:\n{response_text}")
                else:
                    yield event.plain_result(f"命令 '{actual_command}' 已执行。")

        except Exception as e:
            # RCON 连接错误处理
            if client:
                try:
                    await client.close()
                except:
                    pass
            
            # 忽略重启瞬间的连接重置错误
            if is_restart and ("Connection reset" in str(e) or "closed" in str(e) or "Broken pipe" in str(e)):
                # 这里的 catch 是为了防止 stop 指令发出时产生的报错打断流程
                # 但现在的逻辑是先发 stop 再进循环，通常不会走到这里
                # 除非是上面的 loop 中出了非连接性错误
                logger.warning(f"RCON断开 (预期内): {e}")
            else:
                logger.error(f"RCON 错误: {e}")
                yield event.plain_result(f"执行出错: {e}")