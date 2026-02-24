import re
import httpx
import asyncio
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import astrbot.api.message_components as Comp
from astrbot.api import logger

@register("RMT-GRMT", "ZeroStaR", "Moment Tensor Monitoring System", "1.1.2")
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
                # 针对换行问题：使用 \n + \u3000(全角空格) 强行撑开行间距
                return [Comp.Plain(f"\n\u3000{label}\n"), Comp.Image.fromBytes(resp.content)]
        except Exception as e:
            logger.error(f"下载 {label} 失败: {e}")
        return [Comp.Plain(f"\n\u3000{label}\n获取失败\n")]

    @filter.command("rmt")
    async def rmt_now(self, event: AstrMessageEvent, arg: str = ""):
        # 1. 处理 rmt now
        if arg.strip() == "now":
            yield event.plain_result("处理图片中，请稍后..")
            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True) as client:
                tasks = [
                    self._get_img_node(client, "", f"{self.base_url}rmt_10s.png"),
                    self._get_img_node(client, "20~50s", f"{self.base_url}rmt_20s.png")
                ]
                nodes = await asyncio.gather(*tasks)

            chain = [Comp.Plain("RMT v3 当前数据（2分钟延迟，仅供参考）"),Comp.Plain("\n10~50s")]
            for node in nodes: chain.extend(node)
            yield event.chain_result(chain)
            return

        # 2. 处理 rmt report <int>
        if "report" in arg:
            # 使用正则从参数中提取数字
            num_match = re.search(r'report\s*(\d+)', arg)
            index = int(num_match.group(1)) if num_match else 1
            
            yield event.plain_result(f"正在获取第 {index} 个历史报告...")

            async with httpx.AsyncClient(headers=self.headers) as client:
                try:
                    resp = await client.get(f"{self.base_url}list.htm", timeout=10.0)
                    resp.encoding = 'utf-8'
                    html = resp.text

                    # 匹配每一个事件块
                    # 格式：<br><a...>描述</a>...10s链接...20s链接
                    pattern = r'<br><a[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?href="([^"]*)"[^>]*>10s</a>.*?href="([^"]*)"[^>]*>20s</a>'
                    events = re.findall(pattern, html, re.S)

                    if not events:
                        yield event.plain_result("未能在页面中解析到任何事件。")
                        return
                    
                    if index > len(events) or index < 1:
                        yield event.plain_result(f"索引超出范围。当前共有 {len(events)} 个事件。")
                        return

                    # 提取选定的事件 (index 1 是最新)
                    event_data = events[index-1]
                    raw_desc = event_data[1].replace('&nbsp;', ' ').strip()
                    img_10s_rel = event_data[2]
                    img_20s_rel = event_data[3]

                    # 补全 URL (处理相对路径和绝对路径)
                    def fix_url(u): return u if u.startswith("http") else self.base_url + u
                    url_10s = fix_url(img_10s_rel)
                    url_20s = fix_url(img_20s_rel)

                    # 并发下载
                    tasks = [
                        self._get_img_node(client, "", url_10s),
                        self._get_img_node(client, "20s", url_20s)
                    ]
                    nodes = await asyncio.gather(*tasks)

                    # 提取年份
                    year_match = re.search(r'/(\d{4})/', url_10s)
                    year = year_match.group(1) if year_match else ""
                    title = f"{year}/{raw_desc}" if year else raw_desc

                    # 组装消息链
                    # \u3000 是全角空格，能有效防止 NTQQ 客户端将紧随其后的文本与上方合并
                    chain = [Comp.Plain(f"GRMT v3 历史报告\n{title}\n"),Comp.Plain("\n10s")]
                    for node in nodes:
                        chain.extend(node)

                    yield event.chain_result(chain)

                except Exception as e:
                    logger.error(f"解析历史报告失败: {e}")
                    yield event.plain_result(f"获取失败: {str(e)}")