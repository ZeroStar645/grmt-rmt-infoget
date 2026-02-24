import re
import httpx
import asyncio
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import astrbot.api.message_components as Comp
from astrbot.api import logger

@register("RMT-GRMT", "ZeroStaR", "Moment Tensor Monitoring System", "1.1.0")
class EarthMonitorPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.base_url = "https://rmt.earth.sinica.edu.tw/"

    async def _get_img_node(self, client: httpx.AsyncClient, label: str, url: str):
        """获取图片组件"""
        try:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code == 200:
                return [Comp.Plain(f"\n{label}\n"), Comp.Image.fromBytes(resp.content)]
        except Exception as e:
            logger.error(f"下载 {label} 失败: {e}")
        return [Comp.Plain(f"\n{label}\n❌ [获取失败]\n")]

    @filter.command("rmt")
    async def rmt_now(self, event: AstrMessageEvent, arg: str = ""):
        # 兼容旧逻辑 rmt now
        if arg == "now":
            yield event.plain_result("处理图片中，请稍后..")
            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True) as client:
                tasks = [
                    self._get_img_node(client, "10~50s", f"{self.base_url}rmt_10s.png"),
                    self._get_img_node(client, "20~50s", f"{self.base_url}rmt_20s.png")
                ]
                nodes = await asyncio.gather(*tasks)

            chain = [Comp.Plain("RMT v3 当前数据\n（2分钟延迟，仅供参考）\n")]
            for node in nodes: chain.extend(node)
            yield event.chain_result(chain)
            return

        # 新逻辑: rmt report <int>
        if arg.startswith("report"):
            parts = arg.split()
            index = 1
            if len(parts) > 1 and parts[1].isdigit():
                index = int(parts[1])
            
            yield event.plain_result(f"正在获取第 {index} 个历史报告...")

            async with httpx.AsyncClient(headers=self.headers) as client:
                try:
                    # 1. 获取 HTML
                    resp = await client.get(f"{self.base_url}list.htm", timeout=10.0)
                    resp.encoding = 'utf-8' # 确保编码正确
                    html = resp.text

                    # 2. 正则解析所有事件
                    # 匹配模式: <a>时间/震级</a> ... <a>10s</a> ... <a>20s</a>
                    # 这里使用了较宽容的正则来匹配 HTML 结构
                    pattern = r'<br><a.*?href="(.*?)".*?>(.*?)</a>.*?href="(.*?)".*?>10s</a>.*?href="(.*?)".*?>20s</a>'
                    events = re.findall(pattern, html, re.S)

                    if not events or index > len(events):
                        yield event.plain_result(f"❌ 未找到第 {index} 个事件。当前共有 {len(events)} 个记录。")
                        return

                    # 获取选定的事件 (index 是从 1 开始的)
                    target_event = events[index-1]
                    # target_event 结构: (event_url, description, url_10s, url_20s)
                    desc = target_event[1].replace('&nbsp;', ' ').strip()
                    img_10s_rel = target_event[2]
                    img_20s_rel = target_event[3]

                    # 补全 URL
                    img_10s_url = img_10s_rel if img_10s_rel.startswith("http") else self.base_url + img_10s_rel
                    img_20s_url = img_20s_rel if img_20s_rel.startswith("http") else self.base_url + img_20s_rel

                    # 3. 下载图片并构建消息链
                    tasks = [
                        self._get_img_node(client, "10s", img_10s_url),
                        self._get_img_node(client, "20s", img_20s_url)
                    ]
                    nodes = await asyncio.gather(*tasks)

                    # 4. 组装格式
                    # 获取年份信息 (简单从描述或 URL 提取)
                    year_match = re.search(r'/(\d{4})/', img_10s_url)
                    year = year_match.group(1) if year_match else "2026"
                    
                    chain = [Comp.Plain(f"GRMT v3 历史报告\n{year}/{desc}\n")]
                    for node in nodes: chain.extend(node)

                    yield event.chain_result(chain)

                except Exception as e:
                    logger.error(f"解析历史报告失败: {e}")
                    yield event.plain_result("❌ 获取历史报告时发生错误。")