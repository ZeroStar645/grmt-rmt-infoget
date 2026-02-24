import re
import httpx
import asyncio
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import astrbot.api.message_components as Comp
from astrbot.api import logger

@register("RMT-GRMT", "ZeroStaR", "Moment Tensor Monitoring System", "1.2.0")
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
                # 换行补丁：\n + \u3000 (全角空格) 能够强制在很多环境下分行
                return [Comp.Plain(f"\n\u3000{label}\n"), Comp.Image.fromBytes(resp.content)]
        except Exception as e:
            logger.error(f"下载 {label} 失败: {e}")
        return [Comp.Plain(f"\n\u3000{label}\n❌ [获取失败]\n")]

    @filter.command("rmt")
    async def rmt_handler(self, event: AstrMessageEvent, arg: str = ""):
        # 统一清理下空格
        arg_str = arg.strip() if arg else ""
        
        # --- 逻辑 A: rmt now ---
        if arg_str == "now":
            yield event.plain_result("正在获取实时监控，请稍后..")
            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True) as client:
                tasks = [
                    self._get_img_node(client, "10~50s", f"{self.base_url}rmt_10s.png"),
                    self._get_img_node(client, "20~50s", f"{self.base_url}rmt_20s.png")
                ]
                nodes = await asyncio.gather(*tasks)
            chain = [Comp.Plain("RMT v3 当前数据\n（2分钟延迟，仅供参考）")]
            for node in nodes: chain.extend(node)
            yield event.chain_result(chain)
            return

        # --- 逻辑 B: rmt report <int> ---
        if "report" in arg_str:
            # 改进的正则提取：匹配 report 后面跟着的数字
            match = re.search(r"report\s*(\d+)", arg_str)
            index = int(match.group(1)) if match else 1
            
            yield event.plain_result(f"正在获取第 {index} 个历史报告，请稍后..")

            async with httpx.AsyncClient(headers=self.headers) as client:
                try:
                    resp = await client.get(f"{self.base_url}list.htm", timeout=10.0)
                    resp.encoding = 'utf-8'
                    html = resp.text

                    # 匹配 HTML 中的事件组 (基于你提供的 eq_list.html)
                    # 匹配：描述, 10s链接, 20s链接
                    pattern = r'<br><a[^>]*href="[^"]*"[^>]*>(.*?)</a>.*?href="([^"]*)"[^>]*>10s</a>.*?href="([^"]*)"[^>]*>20s</a>'
                    events = re.findall(pattern, html, re.S)

                    if not events:
                        yield event.plain_result("❌ 错误：无法从页面解析到事件列表。")
                        return
                    
                    if index > len(events) or index < 1:
                        yield event.plain_result(f"❌ 索引范围错误：当前共有 {len(events)} 个事件。")
                        return

                    # 获取特定索引的事件
                    selected = events[index - 1]
                    raw_desc = selected[0].replace('&nbsp;', ' ').strip()
                    url_10s = selected[1] if selected[1].startswith("http") else self.base_url + selected[1]
                    url_20s = selected[2] if selected[2].startswith("http") else self.base_url + selected[2]

                    # 下载图片
                    tasks = [
                        self._get_img_node(client, "10s", url_10s),
                        self._get_img_node(client, "20s", url_20s)
                    ]
                    nodes = await asyncio.gather(*tasks)

                    # 尝试从 URL 中提取年份
                    year_match = re.search(r'/(\d{4})/', url_10s)
                    year_prefix = f"{year_match.group(1)}/" if year_match else ""
                    
                    # 构造最终链
                    # 在开头也加入全角空格
                    chain = [Comp.Plain(f"GRMT v3 历史报告\n\u3000{year_prefix}{raw_desc}\n")]
                    for node in nodes:
                        chain.extend(node)

                    yield event.chain_result(chain)

                except Exception as e:
                    logger.error(f"Report 指令执行失败: {e}")
                    yield event.plain_result(f"❌ 发生异常: {str(e)}")