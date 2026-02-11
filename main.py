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
from astrbot.api.message_components import Node, Plain, Image as CompImage
import astrbot.api.message_components as Comp
from bs4 import BeautifulSoup
import re

BASE_URL = "https://missav.ws/cn/"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
BASE_HOST = "client-rapi-missav.recombee.com"
DATABASE_ID = "missav-default"
PUBLIC_TOKEN = "Ikkg568nlM51RHvldlPvc2GzZPE9R4XGzaH9Qj4zK9npbbbTly1gj9K4mgRn0QlV"

@register("astrbot_plugin_missAV", "vmoranv&Foolllll", "MissAV视频信息查询插件", "1.1.0")
class MissAVPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config or {}
        logger.info(f"MissAV 插件配置已加载: {self.config}")

    async def initialize(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        self._clean_cache()

    def _clean_cache(self):
        for f in glob.glob(os.path.join(CACHE_DIR, "*")):
            try:
                os.remove(f)
            except:
                pass

    def _get_proxy(self):
        return self.config.get("missav_proxy", "")

    def _get_blur_level(self):
        return self.config.get("missav_blur_level", 5)



    def _blur_image(self, img_path: str) -> str:
        if not img_path or not os.path.exists(img_path):
            return img_path
        blur = self._get_blur_level()
        if blur <= 0:
            return img_path
        try:
            img = Image.open(img_path)
            blurred = img.filter(ImageFilter.GaussianBlur(radius=blur))
            out_path = img_path.replace(".jpg", "_blur.jpg")
            blurred.save(out_path)
            return out_path
        except Exception as e:
            logger.error(f"模糊图片失败: {e}")
            return img_path

    def _sign_path(self, path: str) -> str:
        ts = int(time.time())
        unsigned = f"/{DATABASE_ID}{path}"
        if "?" in unsigned:
            unsigned += f"&frontend_timestamp={ts}"
        else:
            unsigned += f"?frontend_timestamp={ts}"
        signature = hmac.new(PUBLIC_TOKEN.encode("utf-8"), unsigned.encode("utf-8"), hashlib.sha1).hexdigest()
        return unsigned + f"&frontend_sign={signature}"

    async def _fetch(self, url: str) -> tuple[int, str]:
        proxy = self._get_proxy()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://missav.ws/",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, proxy=proxy if proxy else None) as resp:
                return resp.status, await resp.text()

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
            try:
                async with session.get(url, proxy=proxy if proxy else None, timeout=10) as resp:
                    if resp.status == 200:
                        with open(path, "wb") as f:
                            f.write(await resp.read())
                        return path
                    else:
                        logger.warning(f"下载图片失败: {url}, 状态码: {resp.status}")
            except Exception as e:
                logger.error(f"下载图片发生错误: {url}, 错误: {e}")
        return None

    async def _get_video_info(self, video_id: str):
        url = BASE_URL + video_id
        status, content = await self._fetch(url)
        
        if status == 404:
            return None
            
        soup = BeautifulSoup(content, "lxml")
        
        title_el = soup.find("h1")
        if title_el and ("找不到页面" in title_el.text or "404" in title_el.text):
            return None
        
        # 查找所有信息容器
        info_container = soup.find("div", class_="space-y-2")
        
        # 标题
        title = video_id
        chinese_title = ""
        if info_container:
            for div in info_container.find_all("div", class_="text-secondary"):
                if "标题" in div.text or "Title" in div.text:
                    span = div.find("span", class_="font-medium")
                    if span:
                        title = span.text.strip()
                        break
        
        # 中文标题
        title_el = soup.find("h1")
        if title_el:
            chinese_title = title_el.text.strip()
        
        if title == video_id and chinese_title:
            title = chinese_title
        
        # 查找所有包含信息的div
        video_code = video_id
        publish_date = ""
        manufacturer = ""
        series = ""
        actresses = []
        actors = []
        genres = []
        description = ""
        magnet = ""
        
        # 查找番号
        code_match = re.search(r'[A-Z]{2,}-\d{3,}', video_id.upper())
        if code_match:
            video_code = code_match.group(0)
        
        if info_container:
            for div in info_container.find_all("div", class_="text-secondary"):
                text = div.get_text()
                # 发行日期
                if "发行日期" in text or "Release Date" in text:
                    time_el = div.find("time")
                    if time_el:
                        publish_date = time_el.text.strip()
                # 番号
                if "番号" in text or "Code" in text:
                    span = div.find("span", class_="font-medium")
                    if span:
                        video_code = span.text.strip()
                # 制造商/发行商
                if "メーカー" in text or "Maker" in text or "发行商" in text:
                    a = div.find("a")
                    if a:
                        manufacturer = a.text.strip()
                # 系列
                if "シリーズ" in text or "Series" in text or "系列" in text:
                    a = div.find("a")
                    if a:
                        series = a.text.strip()
                # 女优
                if "女優" in text or "女优" in text or "Actress" in text:
                    for a in div.find_all("a"):
                        actresses.append(a.text.strip())
                # 男优
                if "男優" in text or "男优" in text or "Actor" in text:
                    for a in div.find_all("a"):
                        actors.append(a.text.strip())
                # 类型
                if "类型" in text or "Genre" in text or "類型" in text:
                    for a in div.find_all("a"):
                        genres.append(a.text.strip())
        
        # 磁链
        magnet_el = soup.find("a", href=re.compile(r'^magnet:\?xt='))
        if magnet_el:
            magnet = magnet_el.get("href", "")
        
        # 详情
        desc_el = soup.find("div", class_="text-secondary break-all line-clamp-2")
        if desc_el:
            description = desc_el.text.strip()
        else:
            meta_desc = soup.find("meta", {"name": "description"}) or soup.find("meta", {"property": "og:description"})
            if meta_desc:
                description = meta_desc.get("content", "").strip()
        
        # 封面图
        thumbnail = f"https://fourhoi.com/{video_id.lower()}/cover-n.jpg"
        logger.info(f"最终封面图URL: {thumbnail}")
        
        return {
            "title": title,
            "chinese_title": chinese_title,
            "video_code": video_code,
            "publish_date": publish_date,
            "manufacturer": manufacturer,
            "series": series,
            "actresses": actresses,
            "actors": actors,
            "genres": genres,
            "description": description,
            "magnet": magnet,
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
        """根据视频ID获取视频信息"""
        video_id = video_id.strip().split("/")[-1]
        if not video_id:
            yield event.plain_result("请提供视频ID，例如: /missav ABC-123\u200e")
            return
        self._clean_cache()
        try:
            video = await self._get_video_info(video_id)
            if not video:
                yield event.plain_result(f"未找到番号为 {video_id} 的影片信息。")
                return
            
            # 获取配置的显示字段
            display_fields = self.config.get("display_fields", ["番号", "标题", "中文标题", "发行日期", "详情", "女优", "男优", "类型", "发行商", "系列", "磁链", "封面"])
            
            # 定义字段映射和处理逻辑
            field_map = [
                ("番号", "video_code", lambda x: x),
                ("标题", "title", lambda x: x),
                ("中文标题", "chinese_title", lambda x: x),
                ("发行日期", "publish_date", lambda x: x),
                ("详情", "description", lambda x: x),
                ("女优", "actresses", lambda x: ", ".join(x) if isinstance(x, list) else x),
                ("男优", "actors", lambda x: ", ".join(x) if isinstance(x, list) else x),
                ("类型", "genres", lambda x: ", ".join(x) if isinstance(x, list) else x),
                ("发行商", "manufacturer", lambda x: x),
                ("系列", "series", lambda x: x),
                ("磁链", "magnet", lambda x: x),
            ]

            info_parts = []
            for label, key, formatter in field_map:
                if label in display_fields and video.get(key):
                    val = formatter(video[key])
                    if val:
                        info_parts.append(f"{label}: {val}")
            
            # 过滤掉空的 info_parts 并合并
            info = "\n".join(info_parts)
            info += "\n\u200E"
            
            # 封面处理
            show_cover = "封面" in display_fields
            img_path = None
            if show_cover and video['thumbnail']:
                img_path = await self._download_image(video['thumbnail'], f"{video_id.replace('/', '_')}.jpg")
                if img_path:
                    img_path = self._blur_image(img_path)

            # 合并转发判断
            enable_forward = self.config.get("enable_forward", False)
            if enable_forward and event.get_platform_name() == "aiocqhttp":
                content = [Plain(info)]
                if img_path:
                    content.append(CompImage.fromFileSystem(img_path))
                
                node = Node(
                    uin=event.message_obj.self_id,
                    name="影片信息",
                    content=content
                )
                yield event.chain_result([node])
            else:
                # 普通发送
                if img_path:
                    yield event.chain_result([Comp.Plain(info), Comp.Image.fromFileSystem(img_path)])
                else:
                    msg = info
                    if show_cover and video['thumbnail'] and not img_path:
                        msg += "\n(封面图下载失败)"
                    yield event.plain_result(msg)
                    
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            yield event.plain_result(f"获取失败: {e}\u200E")

    @filter.command("missavsearch")
    async def search_videos(self, event: AstrMessageEvent, query: str = ""):
        """搜索视频"""
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
