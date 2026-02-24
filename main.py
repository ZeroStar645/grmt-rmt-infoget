from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import astrbot.api.message_components as Comp
from astrbot.api import logger
import httpx

@register("RMT-GRMT", "ZeroStaR", "Moment Tensor Monitoring System", "1.0.0")
class EarthMonitorPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 模拟浏览器 Header，防止被拦截
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    async def _get_image_component(self, url: str, label: str):
        """
        手动下载图片并转为消息组件。
        如果失败，返回 Plain 组件提示错误。
        """
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    # 使用 BytesIO 将图片内容包装，避免 Content-Length 截断导致的框架崩溃
                    return [Comp.Plain(f"{label}\n"), Comp.Image.fromBytes(resp.content)]
                else:
                    logger.error(f"图片下载失败: {url} 状态码: {resp.status_code}")
        except Exception as e:
            logger.error(f"请求图片出错: {url}, 错误: {e}")
        
        return [Comp.Plain(f"{label}\n 图片获取失败\n")]

    @filter.command("grmt")
    async def grmt_now(self, event: AstrMessageEvent, arg: str = ""):
        if arg != "now": return
        
        chain = [Comp.Plain("GRMT v3 当前数据（15分钟延迟，仅供参考）\n")]
        tasks = [
            ("BHZ", "https://grmt.earth.sinica.edu.tw/grmt_z.png"),
            ("BHN", "https://grmt.earth.sinica.edu.tw/grmt_n.png"),
            ("BHE", "https://grmt.earth.sinica.edu.tw/grmt_e.png")
        ]
        
        for label, url in tasks:
            components = await self._get_image_component(url, label)
            chain.extend(components)
            
        yield event.chain_result(chain)

    @filter.command("rmt")
    async def rmt_now(self, event: AstrMessageEvent, arg: str = ""):
        if arg != "now": return
        
        chain = [Comp.Plain("RMT v3 当前数据（2分钟延迟，仅供参考）\n")]
        tasks = [
            ("10~50s", "https://rmt.earth.sinica.edu.tw/rmt_10s.png"),
            ("20~50s", "https://rmt.earth.sinica.edu.tw/rmt_20s.png")
        ]
        
        for label, url in tasks:
            components = await self._get_image_component(url, label)
            chain.extend(components)
            
        yield event.chain_result(chain)