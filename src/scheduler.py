"""
调度器模块
负责定期检查RSS feeds
"""
import asyncio
import logging
import re
import hashlib
from typing import List, Dict
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import config
from .database import db
from .rss_parser import parser

logger = logging.getLogger(__name__)

# 全局调度器
scheduler = AsyncIOScheduler()


class RSSChecker:
    """RSS检查器"""
    
    def __init__(self, bot):
        self.bot = bot
        self.is_running = False
    
    async def check_all_feeds(self):
        """检查所有活跃的RSS源"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Starting feed check...")
        
        try:
            feeds = db.get_active_feeds()
            global_keywords = db.get_global_keywords()
            
            for feed in feeds:
                await self.check_feed(feed, global_keywords)
                
        except Exception as e:
            logger.error(f"Error in check_all_feeds: {e}")
        finally:
            self.is_running = False
            # 清理旧记录
            db.clean_old_sent_items(config.history_days)
            logger.info("Feed check completed")
    
    async def check_feed(self, feed, global_keywords):
        """检查单个RSS源"""
        try:
            # 获取feed的特定关键词
            feed_keywords = db.get_feed_keywords(feed.id)
            
            # 合并全局关键词和源特定关键词
            all_keywords = global_keywords + feed_keywords
            
            if not all_keywords:
                logger.debug(f"No keywords for feed: {feed.url}")
                return
            
            # 获取feed内容
            success, feed_data, error = await parser.fetch_feed(feed.url)
            
            if not success:
                logger.warning(f"Failed to fetch feed {feed.url}: {error}")
                db.increment_error(feed.id)
                return
            
            # 更新feed信息
            db.update_feed(feed.id, 
                title=feed_data.get("title"),
                description=feed_data.get("description"),
                last_fetch=datetime.now(),
                error_count=0
            )
            
            # 检查每个条目
            for entry in feed_data.get("entries", []):
                await self.check_entry(feed, entry, all_keywords)
                
        except Exception as e:
            logger.error(f"Error checking feed {feed.url}: {e}")
            db.increment_error(feed.id)
    
    async def check_entry(self, feed, entry, keywords):
        """检查单个条目是否匹配关键词"""
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        url = entry.get("url", "")
        
        if not url:
            return
        
        # 检查是否已发送（去重）
        item_hash = hashlib.sha256(f"{feed.id}:{url}".encode()).hexdigest()
        if db.is_sent(item_hash):
            return
        
        # 检查是否匹配任何关键词
        matched = False
        matched_keywords = []
        
        for kw in keywords:
            if not kw.is_active:
                continue
            
            if self._match_keyword(title, summary, kw):
                matched = True
                matched_keywords.append(kw.keyword)
        
        if matched:
            # 发送通知
            await self.send_notification(feed, entry, matched_keywords)
            
            # 标记为已发送
            db.mark_sent(feed.id, title, url)
    
    def _match_keyword(self, title: str, summary: str, keyword) -> bool:
        """检查是否匹配关键词"""
        text = f"{title} {summary}".lower()
        kw_text = keyword.keyword.lower()
        
        try:
            if keyword.keyword_type == "regex":
                # 正则表达式匹配
                return re.search(keyword.keyword, text, re.IGNORECASE) is not None
            
            elif keyword.keyword_type == "not":
                # NOT 逻辑：包含主关键词但不包含排除关键词
                parts = keyword.keyword.split(" -")
                if len(parts) == 2:
                    main_kw = parts[0].strip().lower()
                    exclude_kw = parts[1].strip().lower()
                    return main_kw in text and exclude_kw not in text
                return kw_text in text
            
            elif keyword.keyword_type == "and":
                # AND 逻辑：必须包含所有关键词
                return all(part.strip().lower() in text for part in keyword.keyword.split("+"))
            
            elif keyword.keyword_type == "or":
                # OR 逻辑：包含任一关键词
                return any(part.strip().lower() in text for part in keyword.keyword.split("|"))
            
            else:
                # 普通匹配
                return kw_text in text
                
        except Exception as e:
            logger.error(f"Error matching keyword {keyword.keyword}: {e}")
            return False
    
    async def send_notification(self, feed, entry, matched_keywords):
        """发送通知到Telegram"""
        try:
            title = entry.get("title", "Untitled")
            url = entry.get("url", "")
            summary = entry.get("summary", "")
            image = entry.get("image")
            
            # 构建消息
            keywords_str = " ".join([f"#{kw.replace(' ', '_')}" for kw in matched_keywords[:5]])
            
            message = f"🔔 <b>关键词匹配</b>\n\n"
            message += f"<b>{title}</b>\n\n"
            message += f"📰 来源: {feed.title or 'Unknown'}\n"
            
            if summary:
                message += f"\n{summary[:200]}...\n"
            
            message += f"\n{keywords_str}"
            
            # 获取所有需要通知的用户
            # 这里简化处理，实际应该存储用户ID列表
            # 默认发送到机器人的管理员
            if config.admin_user_ids:
                for admin_id in config.admin_user_ids:
                    try:
                        if image:
                            await self.bot.send_photo(
                                chat_id=admin_id,
                                photo=image,
                                caption=message,
                                parse_mode="HTML"
                            )
                        else:
                            await self.bot.send_message(
                                chat_id=admin_id,
                                text=message,
                                parse_mode="HTML",
                                disable_web_page_preview=False
                            )
                    except Exception as e:
                        logger.error(f"Error sending notification to {admin_id}: {e}")
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")


# 创建检查器实例
def create_checker(bot):
    """创建RSS检查器"""
    return RSSChecker(bot)


def start_scheduler(bot):
    """启动调度器"""
    checker = create_checker(bot)
    
    # 添加定时任务
    scheduler.add_job(
        checker.check_all_feeds,
        'interval',
        minutes=config.refresh_interval,
        id='feed_check',
        name='Check RSS Feeds'
    )
    
    scheduler.start()
    logger.info(f"Scheduler started with interval: {config.refresh_interval} minutes")
    
    # 立即执行一次检查
    asyncio.create_task(checker.check_all_feeds())
