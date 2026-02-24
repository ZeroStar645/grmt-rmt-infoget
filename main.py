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
        self.headers = {"User-Agent": "Mozilla/5.0..."}

    async def _get_img_node(self, client: httpx.AsyncClient, label: str, url: str):
        """获取图片组件，失败则返回提示文本"""
        try:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code == 200:
                # 重点：在文字组件里直接处理好前后的换行
                return [Comp.Plain(f"\n{label}\n"), Comp.Image.fromBytes(resp.content)]
        except Exception as e:
            logger.error(f"下载 {label} 失败: {e}")
        return [Comp.Plain(f"\n{label}\n❌ [获取失败]\n")]

    @filter.command("rmt")
    async def rmt_now(self, event: AstrMessageEvent, arg: str = ""):
        if arg != "now": return
        
        async with httpx.AsyncClient(headers=self.headers, follow_redirects=True) as client:
            tasks = [
                self._get_img_node(client, "10~50s", "https://rmt.earth.sinica.edu.tw/rmt_10s.png"),
                self._get_img_node(client, "20~50s", "https://rmt.earth.sinica.edu.tw/rmt_20s.png")
            ]
            nodes = await asyncio.gather(*tasks)

        chain = [Comp.Plain("RMT v3 当前数据\n（2分钟延迟，仅供参考）\n")]
        for node in nodes:
            chain.extend(node)

        yield event.chain_result(chain)