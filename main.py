from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp
import aiomcrcon
import asyncio 
import time

@register("mc_rcon", "Remyy", "支持多服务器管理的 RCON 插件", "1.5.0", "https://github.com/Remyy-y/astrbot_plugin_mcm")
class MCRconPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        logger.info("MC RCON 多服插件已加载！")

    @filter.command("mc-command", alias={'mc'})
    async def handle_mc_command(self, event: AstrMessageEvent):
        # 获取配置中的服务器列表
        servers_config = self.config.get("servers", [])
        
        if not servers_config:
            yield event.plain_result("❌ 错误：插件未配置任何服务器！请前往设置页面添加服务器。")
            return

        # 解析用户指令
        raw_message = event.message_str.strip()
        # 我们这里 maxsplit=2，分成：[指令头, 服务器名, 具体指令]
        # 例如: "/mc sky restart" -> ["/mc", "sky", "restart"]
        parts = raw_message.split(maxsplit=2)
        
        # --- 帮助与列表逻辑 ---
        if len(parts) < 2:
            # 用户只输入了 /mc
            server_names = [s.get('name', '未命名') for s in servers_config]
            help_msg = (
                "指令格式错误。请使用：\n"
                "/mc <服务器名> <指令>\n\n"
                "当前可用服务器:\n" + "、".join(server_names)
            )
            yield event.plain_result(help_msg)
            return

        target_name = parts[1] # 获取目标服务器名称 (如 sky)

        # 特殊指令：/mc servers 查看列表
        if target_name == "servers":
            server_list_str = "\n".join([f"- {s.get('name')} ({s.get('host')}:{s.get('port')})" for s in servers_config])
            yield event.plain_result(f"已配置的服务器列表：\n{server_list_str}")
            return

        # 检查是否缺少具体指令 (如用户只输入了 /mc sky)
        if len(parts) < 3:
            yield event.plain_result(f"请输入要对 '{target_name}' 执行的具体指令，例如：/mc {target_name} list")
            return

        user_command = parts[2].strip() # 实际指令部分 (如 restart 或 list)
        
        # --- 查找对应的服务器配置 ---
        target_server = None
        for s in servers_config:
            if s.get("name") == target_name:
                target_server = s
                break
        
        if not target_server:
            yield event.plain_result(f"❌ 找不到名为 '{target_name}' 的服务器配置。")
            return

        # 提取连接信息
        host = target_server.get("host")
        port = target_server.get("port", 25575)
        password = target_server.get("password")

        if not password:
            yield event.plain_result(f"❌ 服务器 '{target_name}' 未配置 RCON 密码！")
            return

        # --- 以下逻辑复用之前的重启/指令处理 (已适配新变量) ---
        actual_command = user_command   
        is_restart = False

        # 快捷指令映射
        if user_command in ["在线", "online", "list"]:
            actual_command = "list"
        elif user_command in ["重启", "restart"]:
            is_restart = True
            actual_command = "stop"

        client = None
        try:
            # 1. 连接 RCON
            client = aiomcrcon.Client(host, port, password)
            await client.connect()
            
            # 2. 重启逻辑
            if is_restart:
                logger.info(f"[{target_name}] 执行重启流程: {host}:{port}")
                
                # 倒计时广播
                await client.send_cmd("say §cServer is restarting in 3 seconds...")
                await asyncio.sleep(1)
                await client.send_cmd("say §c2...")
                await asyncio.sleep(1)
                await client.send_cmd("say §c1...")
                await asyncio.sleep(1)
                
                await client.send_cmd("save-all")
                await client.send_cmd("stop") # 发送关闭指令
                
                await client.close()
                client = None

                # 告知用户并保持会话
                yield event.plain_result(f"⏳ [{target_name}] 正在重启...\n(Bot 将保持检测直至上线)")

                # 3. 阻塞检测循环
                await asyncio.sleep(15) # 等待关闭

                start_wait_time = time.time()
                max_retries = 60
                
                for i in range(max_retries):
                    # 超时检查
                    if time.time() - start_wait_time > 280:
                        yield event.plain_result(f"⚠️ [{target_name}] 等待超时，请手动检查。")
                        return

                    check_client = None
                    try:
                        check_client = aiomcrcon.Client(host, port, password)
                        await check_client.connect()
                        # 连接成功即代表启动完成
                        await check_client.close()
                        
                        elapsed = int(time.time() - start_wait_time)
                        logger.info(f"[{target_name}] 重启检测成功，耗时 {elapsed}s")
                        
                        yield event.plain_result(f"✅ [{target_name}] 重启成功！\n⏱️ 耗时约 {elapsed} 秒，可以在线了！")
                        return 
                        
                    except Exception:
                        if i % 4 == 0:
                            logger.info(f"[{target_name}] 等待启动中...")
                        if check_client:
                            try:
                                await check_client.close()
                            except:
                                pass
                        await asyncio.sleep(5)
                
                yield event.plain_result(f"⚠️ [{target_name}] 检测循环结束，未能连接。")
                return

            else:
                # 普通指令处理
                response = await client.send_cmd(actual_command)
                await client.close()
                
                if isinstance(response, tuple):
                    response_text = response[0]
                else:
                    response_text = response

                if response_text:
                    # 在回复前加上服务器名字，区分更清晰
                    header = f"[{target_name}] 响应:\n"
                    yield event.plain_result(header + response_text)
                else:
                    yield event.plain_result(f"[{target_name}] 命令 '{actual_command}' 已执行。")

        except Exception as e:
            if client:
                try:
                    await client.close()
                except:
                    pass
            
            # 忽略重启瞬间的错误
            if is_restart and ("Connection reset" in str(e) or "closed" in str(e) or "Broken pipe" in str(e)):
                logger.warning(f"RCON断开 (预期内): {e}")
            else:
                logger.error(f"[{target_name}] RCON 错误: {e}")
                yield event.plain_result(f"❌ [{target_name}] 执行出错: {e}")