from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import astrbot.api.message_components as Comp
from astrbot.api import logger
import httpx
import asyncio
@register("RMT-GRMT", "ZeroStaR", "Moment Tensor Monitoring System", "1.0.0")
class EarthMonitorPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    async def _fetch_single_image(self, client: httpx.AsyncClient, label: str, url: str):
        """下载图片并封装，确保文字与图片之间、图片之后都有换行"""
        try:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code == 200:
                # 在 label 前后都加换行，确保它独立成行
                return [
                    Comp.Plain(f"\n{label}\n"), 
                    Comp.Image.fromBytes(resp.content)
                ]
        except Exception as e:
            logger.error(f"并发请求图片失败: {url}, {e}")
        
        return [Comp.Plain(f"\n{label}\n❌ [图片获取失败]\n")]

    @filter.command("grmt")
    async def grmt_now(self, event: AstrMessageEvent, arg: str = ""):
        if arg != "now": return
        yield event.plain_result("处理图片中，请稍后..")
        tasks_info = [
            ("BHZ", "https://grmt.earth.sinica.edu.tw/grmt_z.png"),
            ("BHN", "https://grmt.earth.sinica.edu.tw/grmt_n.png"),
            ("BHE", "https://grmt.earth.sinica.edu.tw/grmt_e.png")
        ]

        async with httpx.AsyncClient(headers=self.headers, follow_redirects=True) as client:
            tasks = [self._fetch_single_image(client, label, url) for label, url in tasks_info]
            results = await asyncio.gather(*tasks)

        # 头部信息增加双换行，强制撑开空间
        chain = [Comp.Plain("GRMT v3 当前数据\n（15分钟延迟，仅供参考）\n")]
        for res in results:
            chain.extend(res)
            
        yield event.chain_result(chain)

    @filter.command("rmt")
    async def rmt_now(self, event: AstrMessageEvent, arg: str = ""):
        if arg != "now": return
        yield event.plain_result("处理图片中，请稍后..")
        tasks_info = [
            ("10~50s", "https://rmt.earth.sinica.edu.tw/rmt_10s.png"),
            ("20~50s", "https://rmt.earth.sinica.edu.tw/rmt_20s.png")
        ]

        async with httpx.AsyncClient(headers=self.headers, follow_redirects=True) as client:
            tasks = [self._fetch_single_image(client, label, url) for label, url in tasks_info]
            results = await asyncio.gather(*tasks)

        chain = [Comp.Plain("RMT v3 当前数据\n（2分钟延迟，仅供参考）\n")]
        for res in results:
            chain.extend(res)
            
        yield event.chain_result(chain)