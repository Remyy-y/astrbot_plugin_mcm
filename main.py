from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp
import aiomcrcon
import asyncio 
import time

@register("mc_rcon", "Remyy", "支持多服务器管理的 RCON 插件", "1.6.0", "https://github.com/Remyy-y/astrbot_plugin_mcm")
class MCRconPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        logger.info("MC RCON 多服插件已加载！")

    def get_all_servers(self):
        """辅助函数：从配置中提取所有已启用的服务器"""
        servers = []
        # 遍历预设的三个配置槽位
        for key in ["server_1", "server_2", "server_3"]:
            svr_conf = self.config.get(key)
            # 只有当配置存在，且 'enable' 为 True 时才加载
            if svr_conf and svr_conf.get("enable", False):
                servers.append(svr_conf)
        return servers

    @filter.command("mc-command", alias={'mc'})
    async def handle_mc_command(self, event: AstrMessageEvent):
        # 获取所有启用的服务器
        servers_config = self.get_all_servers()
        
        if not servers_config:
            yield event.plain_result("❌ 错误：未启用任何服务器！请在插件配置中开启至少一个服务器。")
            return

        raw_message = event.message_str.strip()
        parts = raw_message.split(maxsplit=2)
        
        # --- 帮助与列表逻辑 ---
        if len(parts) < 2:
            server_names = [s.get('name', '未命名') for s in servers_config]
            help_msg = (
                "指令格式错误。请使用：\n"
                "/mc <服务器名> <指令>\n\n"
                "当前可用服务器:\n" + "、".join(server_names)
            )
            yield event.plain_result(help_msg)
            return

        target_name = parts[1] 

        # 列表指令
        if target_name == "servers":
            server_list_str = "\n".join([f"- {s.get('name')} ({s.get('host')}:{s.get('port')})" for s in servers_config])
            yield event.plain_result(f"已启用服务器：\n{server_list_str}")
            return

        # 检查是否缺少具体指令
        if len(parts) < 3:
            yield event.plain_result(f"请输入具体指令，例如：/mc {target_name} list")
            return

        user_command = parts[2].strip()
        
        # --- 查找对应的服务器配置 ---
        target_server = None
        for s in servers_config:
            if s.get("name") == target_name:
                target_server = s
                break
        
        if not target_server:
            yield event.plain_result(f"❌ 找不到名为 '{target_name}' 的服务器(或未启用)。")
            return

        host = target_server.get("host")
        port = target_server.get("port", 25575)
        password = target_server.get("password")

        if not password:
            yield event.plain_result(f"❌ 服务器 '{target_name}' 未配置密码！")
            return

        # --- 以下逻辑保持不变 ---
        actual_command = user_command   
        is_restart = False

        if user_command in ["在线", "online", "list"]:
            actual_command = "list"
        elif user_command in ["重启", "restart"]:
            is_restart = True
            actual_command = "stop"

        client = None
        try:
            client = aiomcrcon.Client(host, port, password)
            await client.connect()
            
            if is_restart:
                logger.info(f"[{target_name}] 执行重启: {host}:{port}")
                await client.send_cmd("say §cServer is restarting in 3 seconds...")
                await asyncio.sleep(1)
                await client.send_cmd("say §c2...")
                await asyncio.sleep(1)
                await client.send_cmd("say §c1...")
                await asyncio.sleep(1)
                await client.send_cmd("save-all")
                await client.send_cmd("stop")
                await client.close()
                client = None

                yield event.plain_result(f"⏳ [{target_name}] 正在重启...\n(Bot 将保持检测)")

                await asyncio.sleep(15)

                start_wait_time = time.time()
                for i in range(60): # 5分钟超时
                    if time.time() - start_wait_time > 280:
                        yield event.plain_result(f"⚠️ [{target_name}] 等待超时。")
                        return

                    check_client = None
                    try:
                        check_client = aiomcrcon.Client(host, port, password)
                        await check_client.connect()
                        await check_client.close()
                        
                        elapsed = int(time.time() - start_wait_time)
                        yield event.plain_result(f"✅ [{target_name}] 重启成功！耗时约 {elapsed} 秒。")
                        return 
                    except Exception:
                        if i % 4 == 0: logger.info(f"[{target_name}] 等待启动...")
                        if check_client:
                            try: await check_client.close()
                            except: pass
                        await asyncio.sleep(5)
                
                yield event.plain_result(f"⚠️ [{target_name}] 未能连接。")
                return

            else:
                response = await client.send_cmd(actual_command)
                await client.close()
                
                if isinstance(response, tuple):
                    response_text = response[0]
                else:
                    response_text = response

                if response_text:
                    header = f"[{target_name}] 响应:\n"
                    yield event.plain_result(header + response_text)
                else:
                    yield event.plain_result(f"[{target_name}] 已执行。")

        except Exception as e:
            if client:
                try: await client.close()
                except: pass
            
            if is_restart and ("Connection reset" in str(e) or "closed" in str(e) or "Broken pipe" in str(e)):
                pass
            else:
                logger.error(f"[{target_name}] 错误: {e}")
                yield event.plain_result(f"❌ [{target_name}] 错误: {e}")