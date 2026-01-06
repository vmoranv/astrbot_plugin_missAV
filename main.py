import os
import glob
import time
import hmac
import hashlib
import aiohttp
from PIL import Image, ImageFilter
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp
from bs4 import BeautifulSoup
import re

BASE_URL = "https://missav.ws/en/"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
BASE_HOST = "client-rapi-missav.recombee.com"
DATABASE_ID = "missav-default"
PUBLIC_TOKEN = "Ikkg568nlM51RHvldlPvc2GzZPE9R4XGzaH9Qj4zK9npbbbTly1gj9K4mgRn0QlV"

@register("missav", "vmoranv", "MissAV视频信息查询插件", "1.0.0")
class MissAVPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = None

    async def initialize(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        self._clean_cache()
        self.config = self.context.get_config()

    def _clean_cache(self):
        for f in glob.glob(os.path.join(CACHE_DIR, "*")):
            try:
                os.remove(f)
            except:
                pass

    def _get_proxy(self):
        cfg = self.config or {}
        return cfg.get("missav_proxy", "")

    def _get_blur_level(self):
        cfg = self.config or {}
        return cfg.get("missav_blur_level", 20)

    def _blur_image(self, img_path: str) -> str:
        blur = self._get_blur_level()
        if blur <= 0:
            return img_path
        img = Image.open(img_path)
        blurred = img.filter(ImageFilter.GaussianBlur(radius=blur))
        out_path = img_path.replace(".jpg", "_blur.jpg")
        blurred.save(out_path)
        return out_path

    def _sign_path(self, path: str) -> str:
        ts = int(time.time())
        unsigned = f"/{DATABASE_ID}{path}"
        if "?" in unsigned:
            unsigned += f"&frontend_timestamp={ts}"
        else:
            unsigned += f"?frontend_timestamp={ts}"
        signature = hmac.new(PUBLIC_TOKEN.encode("utf-8"), unsigned.encode("utf-8"), hashlib.sha1).hexdigest()
        return unsigned + f"&frontend_sign={signature}"

    async def _fetch(self, url: str) -> str:
        proxy = self._get_proxy()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://missav.ws/",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, proxy=proxy if proxy else None) as resp:
                return await resp.text()

    async def _post_json(self, path: str, json_body: dict):
        signed_path = self._sign_path(path)
        url = f"https://{BASE_HOST}{signed_path}"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        proxy = self._get_proxy()
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=json_body, headers=headers, proxy=proxy if proxy else None) as resp:
                return await resp.json()

    async def _download_image(self, url: str, filename: str) -> str:
        path = os.path.join(CACHE_DIR, filename)
        proxy = self._get_proxy()
        async with aiohttp.ClientSession() as session:
            async with session.get(url, proxy=proxy if proxy else None) as resp:
                if resp.status == 200:
                    with open(path, "wb") as f:
                        f.write(await resp.read())
        return path

    async def _get_video_info(self, video_id: str):
        url = BASE_URL + video_id
        content = await self._fetch(url)
        soup = BeautifulSoup(content, "lxml")
        
        # 标题
        title_el = soup.find("h1")
        title = title_el.text.strip() if title_el else video_id
        
        # 查找所有包含信息的div
        video_code = video_id
        publish_date = ""
        manufacturer = ""
        series = ""
        actresses = []
        
        # 查找番号 - 通常在页面中有明确标识
        code_match = re.search(r'[A-Z]{2,}-\d{3,}', video_id.upper())
        if code_match:
            video_code = code_match.group(0)
        
        # 查找所有text-secondary的div
        for div in soup.find_all("div", class_="text-secondary"):
            text = div.get_text()
            # 发布日期
            time_el = div.find("time")
            if time_el:
                publish_date = time_el.text.strip()
            # 番号
            if "番号" in text or "Code" in text:
                span = div.find("span", class_="font-medium")
                if span:
                    video_code = span.text.strip()
            # 制造商/厂商
            if "メーカー" in text or "Maker" in text or "制造商" in text:
                a = div.find("a")
                if a:
                    manufacturer = a.text.strip()
            # 系列
            if "シリーズ" in text or "Series" in text or "系列" in text:
                a = div.find("a")
                if a:
                    series = a.text.strip()
            # 女优
            if "女優" in text or "Actress" in text:
                for a in div.find_all("a"):
                    actresses.append(a.text.strip())
        
        # 封面图 - 直接用video_id构造URL
        # 格式: https://fourhoi.com/{video_id}/cover-t.jpg
        thumbnail = f"https://fourhoi.com/{video_id}/cover-t.jpg"
        logger.info(f"封面图URL: {thumbnail}")
        
        return {
            "title": title,
            "video_code": video_code,
            "publish_date": publish_date,
            "manufacturer": manufacturer,
            "series": series,
            "actresses": actresses,
            "thumbnail": thumbnail
        }

    async def _search(self, query: str, count: int = 10):
        from urllib.parse import quote
        path = f"/search/users/{quote('anonymous', safe='')}/items/"
        body = {"searchQuery": query, "count": count, "cascadeCreate": True, "returnProperties": True}
        data = await self._post_json(path, body)
        videos = data.get("recomms", [])
        results = []
        for v in videos[:count]:
            results.append({"id": v["id"], "title": v.get("values", {}).get("title", v["id"])})
        return results

    @filter.command("missav")
    async def get_video_info(self, event: AstrMessageEvent, video_id: str = ""):
        """根据视频ID获取视频信息\u200E"""
        if not video_id:
            yield event.plain_result("请提供视频ID，例如: /missav ABC-123\u200E")
            return
        self._clean_cache()
        try:
            video = await self._get_video_info(video_id)
            info = f"标题: {video['title']}\n"
            info += f"番号: {video['video_code']}\n"
            if video['publish_date']:
                info += f"发布日期: {video['publish_date']}\n"
            if video.get('actresses'):
                info += f"女优: {', '.join(video['actresses'])}\n"
            if video['manufacturer']:
                info += f"制造商: {video['manufacturer']}\n"
            if video['series']:
                info += f"系列: {video['series']}\n"
            info += "\u200E"
            if video['thumbnail']:
                img_path = await self._download_image(video['thumbnail'], f"{video_id.replace('/', '_')}.jpg")
                img_path = self._blur_image(img_path)
                yield event.chain_result([Comp.Plain(info), Comp.Image.fromFileSystem(img_path)])
            else:
                yield event.plain_result(info)
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            yield event.plain_result(f"获取失败: {e}\u200E")

    @filter.command("missavsearch")
    async def search_videos(self, event: AstrMessageEvent, query: str = ""):
        """搜索视频\u200E"""
        if not query:
            yield event.plain_result("请提供搜索关键词，例如: /missavsearch 关键词\u200E")
            return
        self._clean_cache()
        try:
            results = await self._search(query, 10)
            if results:
                lines = [f"{r['id']} - {r['title']}" for r in results]
                yield event.plain_result("搜索结果:\n" + "\n".join(lines) + "\u200E")
            else:
                yield event.plain_result("未找到结果\u200E")
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            yield event.plain_result(f"搜索失败: {e}\u200E")

    async def terminate(self):
        self._clean_cache()
