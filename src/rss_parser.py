"""
RSS解析模块
负责获取和解析RSS/Atom feeds
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import feedparser
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class RSSParser:
    """RSS解析器"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "RSS-Sentinel-Bot/1.0"
        }
    
    async def fetch_feed(self, url: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        获取并解析RSS feed
        
        Returns:
            (success, feed_data, error_message)
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # 解析feed
                feed = feedparser.parse(response.text)
                
                if feed.bozo and not feed.entries:
                    return False, None, "Invalid RSS feed format"
                
                # 提取feed信息
                feed_info = {
                    "title": feed.feed.get("title", "Unknown"),
                    "description": feed.feed.get("description", ""),
                    "link": feed.feed.get("link", ""),
                    "entries": []
                }
                
                # 提取条目
                for entry in feed.entries[:50]:
                    item = self._parse_entry(entry)
                    if item:
                        feed_info["entries"].append(item)
                
                return True, feed_info, None
                
        except httpx.TimeoutException:
            return False, None, "Request timeout"
        except httpx.HTTPStatusError as e:
            return False, None, f"HTTP error: {e.response.status_code}"
        except Exception as e:
            logger.error(f"Error fetching feed {url}: {e}")
            return False, None, str(e)
    
    def _parse_entry(self, entry) -> Optional[Dict]:
        """解析单个条目"""
        try:
            # 获取标题
            title = entry.get("title", "Untitled").strip()
            if not title:
                return None
            
            # 获取链接
            link = ""
            if hasattr(entry, "links") and entry.links:
                for l in entry.links:
                    if l.get("type", "").startswith("text/html"):
                        link = l.get("href", "")
                        break
            if not link:
                link = entry.get("link", "")
            
            # 获取摘要
            summary = ""
            if hasattr(entry, "summary"):
                summary = entry.summary
            elif hasattr(entry, "description"):
                summary = entry.description
            
            # 清理HTML标签
            summary = self._clean_html(summary)
            
            # 获取发布时间
            published = None
            if hasattr(entry, "published"):
                try:
                    published = entry.published
                except:
                    pass
            elif hasattr(entry, "updated"):
                try:
                    published = entry.updated
                except:
                    pass
            
            # 获取图片
            image = self._extract_image(entry)
            
            return {
                "title": title,
                "link": link,
                "summary": summary[:500],
                "published": published,
                "image": image
            }
        except Exception as e:
            logger.error(f"Error parsing entry: {e}")
            return None
    
    def _clean_html(self, text: str) -> str:
        """清理HTML标签"""
        if not text:
            return ""
        soup = BeautifulSoup(text, "lxml")
        return soup.get_text(separator=" ", strip=True)
    
    def _extract_image(self, entry) -> Optional[str]:
        """提取图片URL"""
        # 检查 media:content
        if hasattr(entry, "media_content") and entry.media_content:
            for m in entry.media_content:
                if m.get("type", "").startswith("image/"):
                    return m.get("url")
        
        # 检查 media:thumbnail
        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            return entry.media_thumbnail[0].get("url")
        
        # 检查 enclosures
        if hasattr(entry, "enclosures") and entry.enclosures:
            for e in entry.enclosures:
                if e.get("type", "").startswith("image/"):
                    return e.get("href")
        
        # 从内容中提取第一张图片
        if hasattr(entry, "content") and entry.content:
            content = entry.content[0].value
            soup = BeautifulSoup(content, "lxml")
            img = soup.find("img")
            if img:
                return img.get("src")
        
        return None
    
    async def discover_rss(self, url: str) -> Optional[str]:
        """
        自动发现RSS链接
        
        Returns:
            RSS URL if found, None otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "lxml")
                
                # 查找 RSS link 标签
                for link in soup.find_all("link", type=["application/rss+xml", "application/atom+xml"]):
                    href = link.get("href")
                    if href:
                        return href if href.startswith("http") else f"{url.rstrip('/')}/{href}"
                
                # 查找常见的RSS路径
                common_paths = ["/rss", "/feed", "/atom.xml", "/rss.xml", "/feed.xml", "/blog/feed"]
                for path in common_paths:
                    test_url = url.rstrip("/") + path
                    try:
                        resp = await client.get(test_url, follow_redirects=True)
                        if resp.status_code == 200 and ("rss" in resp.headers.get("Content-Type", "") or "atom" in resp.headers.get("Content-Type", "")):
                            return test_url
                    except:
                        continue
                
                return None
                
        except Exception as e:
            logger.error(f"Error discovering RSS for {url}: {e}")
            return None


# 全局解析器实例
parser = RSSParser()
