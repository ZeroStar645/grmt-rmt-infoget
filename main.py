import re
import httpx
import asyncio
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import astrbot.api.message_components as Comp
from astrbot.api import logger

@register("RMT-GRMT", "ZeroStaR", "Moment Tensor Monitoring System", "1.3.0")
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
                # 换行增强补丁：使用 \n + \u3000(全角空格) 强行占据一整行，防止被合并
                return [Comp.Plain(f"\n\u3000{label}\n"), Comp.Image.fromBytes(resp.content)]
        except Exception as e:
            logger.error(f"下载 {label} 失败: {e}")
        return [Comp.Plain(f"\n\u3000{label}\n❌ [图片获取失败]\n")]

    @filter.command("rmt")
    async def rmt_handler(self, event: AstrMessageEvent, arg: str = ""):
        # 获取最原始的用户文本，例如 "/rmt report 5"
        full_text = event.message_str.strip()
        
        # --- 1. 处理 rmt now ---
        if "now" in full_text:
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

        # --- 2. 处理 rmt report <int> ---
        if "report" in full_text:
            # 使用更强大的正则提取数字：匹配 report 后面可能存在的空格及数字
            index_match = re.search(r"report\s*(\d+)", full_text)
            index = int(index_match.group(1)) if index_match else 1
            
            yield event.plain_result(f"🔍 正在检索第 {index} 个历史报告...")

            async with httpx.AsyncClient(headers=self.headers) as client:
                try:
                    resp = await client.get(f"{self.base_url}list.htm", timeout=10.0)
                    resp.encoding = 'utf-8'
                    html = resp.text

                    # 针对 eq_list.html 的结构进行精准匹配
                    # 匹配组：1.描述文本, 2.10s链接, 3.20s链接
                    pattern = r'<br><a[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?href="([^"]*)"[^>]*>10s</a>.*?href="([^"]*)"[^>]*>20s</a>'
                    events = re.findall(pattern, html, re.S)

                    if not events:
                        yield event.plain_result("❌ 解析失败：未能在页面中找到事件列表。")
                        return
                    
                    if index > len(events) or index < 1:
                        yield event.plain_result(f"❌ 范围错误：当前仅有 {len(events)} 个事件。")
                        return

                    # 提取选定索引的事件数据
                    selected_data = events[index - 1]
                    raw_desc = selected_data[1].replace('&nbsp;', ' ').strip()
                    # 补全 URL
                    def fix_url(u): return u if u.startswith("http") else self.base_url + u
                    url_10s = fix_url(selected_data[2])
                    url_20s = fix_url(selected_data[3])

                    # 并发下载图片
                    tasks = [
                        self._get_img_node(client, "10s", url_10s),
                        self._get_img_node(client, "20s", url_20s)
                    ]
                    nodes = await asyncio.gather(*tasks)

                    # 提取年份
                    year_match = re.search(r'/(\d{4})/', url_10s)
                    year_str = f"{year_match.group(1)}/" if year_match else ""
                    
                    # 构造最终链，开头加入 \u3000 确保页眉与后续内容的间距
                    chain = [Comp.Plain(f"GRMT v3 历史报告\n\u3000{year_str}{raw_desc}\n")]
                    for node in nodes:
                        chain.extend(node)

                    yield event.chain_result(chain)

                except Exception as e:
                    logger.error(f"历史报告获取失败: {e}")
                    yield event.plain_result(f"❌ 运行出错: {str(e)}")