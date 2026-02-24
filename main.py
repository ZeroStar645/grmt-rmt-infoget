from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import astrbot.api.message_components as Comp
from astrbot.api import logger
import httpx

@register("RMT-GRMT", "ZeroStaR", "Moment Tensor Monitoring System", "1.0.0")
class EarthMonitorPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def _safe_add_image(self, chain: list, url: str, label: str):
        """尝试添加图片，失败则添加错误提示"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.head(url)
                if resp.status_code == 200:
                    chain.append(Comp.Plain(f"{label}\n"))
                    chain.append(Comp.Image.fromURL(url))
                    return
        except Exception as e:
            logger.error(f"图片请求异常: {url}, {e}")
        
        # 失败处理
        chain.append(Comp.Plain(f"{label}\n获取图片失败\n"))

    @filter.command("grmt")
    async def grmt_now(self, event: AstrMessageEvent, arg: str = ""):
        """获取 GRMT 数据: /grmt now"""
        if arg != "now": return
        
        chain = [Comp.Plain("GRMT v3 当前数据（15分钟延迟，仅供参考）\n")]
        
        # 按照你要求的顺序依次添加
        tasks = [
            ("BHZ", "https://grmt.earth.sinica.edu.tw/grmt_z.png"),
            ("BHN", "https://grmt.earth.sinica.edu.tw/grmt_n.png"),
            ("BHE", "https://grmt.earth.sinica.edu.tw/grmt_e.png")
        ]
        
        for label, url in tasks:
            await self._safe_add_image(chain, url, label)
            
        yield event.chain_result(chain)

    @filter.command("rmt")
    async def rmt_now(self, event: AstrMessageEvent, arg: str = ""):
        """获取 RMT 数据: /rmt now"""
        if arg != "now": return
        
        chain = [Comp.Plain("RMT v3 当前数据（2分钟延迟，仅供参考）\n")]
        
        tasks = [
            ("10~50s", "https://rmt.earth.sinica.edu.tw/rmt_10s.png"),
            ("20~50s", "https://rmt.earth.sinica.edu.tw/rmt_20s.png")
        ]
        
        for label, url in tasks:
            await self._safe_add_image(chain, url, label)
            
        yield event.chain_result(chain)