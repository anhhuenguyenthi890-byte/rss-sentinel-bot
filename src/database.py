"""
数据库模块
使用SQLAlchemy进行数据库操作
"""
import hashlib
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.sql import func

from .config import config

logger = logging.getLogger(__name__)

Base = declarative_base()


class Feed(Base):
    """RSS源模型"""
    __tablename__ = "feeds"
    
    id = Column(Integer, primary_key=True)
    url = Column(String(500), unique=True, nullable=False, index=True)
    title = Column(String(200))
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    error_count = Column(Integer, default=0)
    last_fetch = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关联
    keywords = relationship("Keyword", back_populates="feed", cascade="all, delete-orphan")


class Keyword(Base):
    """关键词模型"""
    __tablename__ = "keywords"
    
    id = Column(Integer, primary_key=True)
    feed_id = Column(Integer, ForeignKey("feeds.id", ondelete="CASCADE"), nullable=True)
    keyword = Column(String(200), nullable=False)
    keyword_type = Column(String(20), default="normal")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    
    # 关联
    feed = relationship("Feed", back_populates="keywords")


class SentItem(Base):
    """已发送条目记录（用于去重）"""
    __tablename__ = "sent_items"
    
    id = Column(Integer, primary_key=True)
    item_hash = Column(String(64), unique=True, index=True)
    feed_id = Column(Integer, ForeignKey("feeds.id", ondelete="CASCADE"))
    title = Column(String(500))
    url = Column(String(500))
    sent_at = Column(DateTime, default=func.now())


class UserSettings(Base):
    """用户设置"""
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    digest_mode = Column(Boolean, default=False)
    notify_with_image = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Database:
    """数据库管理类"""
    
    def __init__(self, db_url: str = None):
        self.db_url = db_url or config.database_url
        self.engine = create_engine(self.db_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)
        logger.info(f"Database initialized: {self.db_url}")
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()
    
    # ============ Feed 操作 ============
    
    def add_feed(self, url: str, title: str = None, description: str = None) -> Feed:
        """添加RSS源"""
        session = self.get_session()
        try:
            existing = session.query(Feed).filter(Feed.url == url).first()
            if existing:
                return existing
            
            feed = Feed(url=url, title=title, description=description)
            session.add(feed)
            session.commit()
            session.refresh(feed)
            logger.info(f"Added feed: {url}")
            return feed
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding feed: {e}")
            raise
        finally:
            session.close()
    
    def get_all_feeds(self) -> List[Feed]:
        """获取所有RSS源"""
        session = self.get_session()
        try:
            return session.query(Feed).all()
        finally:
            session.close()
    
    def get_active_feeds(self) -> List[Feed]:
        """获取活跃的RSS源"""
        session = self.get_session()
        try:
            return session.query(Feed).filter(Feed.is_active == True).all()
        finally:
            session.close()
    
    def get_feed_by_id(self, feed_id: int) -> Optional[Feed]:
        """根据ID获取RSS源"""
        session = self.get_session()
        try:
            return session.query(Feed).filter(Feed.id == feed_id).first()
        finally:
            session.close()
    
    def update_feed(self, feed_id: int, **kwargs):
        """更新RSS源"""
        session = self.get_session()
        try:
            feed = session.query(Feed).filter(Feed.id == feed_id).first()
            if feed:
                for key, value in kwargs.items():
                    setattr(feed, key, value)
                session.commit()
        finally:
            session.close()
    
    def delete_feed(self, feed_id: int):
        """删除RSS源"""
        session = self.get_session()
        try:
            feed = session.query(Feed).filter(Feed.id == feed_id).first()
            if feed:
                session.delete(feed)
                session.commit()
                logger.info(f"Deleted feed: {feed_id}")
        finally:
            session.close()
    
    def increment_error(self, feed_id: int):
        """增加错误计数"""
        session = self.get_session()
        try:
            feed = session.query(Feed).filter(Feed.id == feed_id).first()
            if feed:
                feed.error_count += 1
                if feed.error_count >= 10:
                    feed.is_active = False
                    logger.warning(f"Feed disabled due to too many errors: {feed.url}")
                session.commit()
        finally:
            session.close()
    
    # ============ Keyword 操作 ============
    
    def add_keyword(self, keyword: str, feed_id: int = None, keyword_type: str = "normal") -> Keyword:
        """添加关键词"""
        session = self.get_session()
        try:
            # 解析关键词类型
            if keyword.startswith("regex:"):
                keyword_type = "regex"
                keyword = keyword[7:]
            elif keyword.startswith("+"):
                keyword_type = "and"
                keyword = keyword[1:]
            elif keyword.startswith("|"):
                keyword_type = "or"
                keyword = keyword[1:]
            elif " -" in keyword:
                keyword_type = "not"
            
            kw = Keyword(keyword=keyword, feed_id=feed_id, keyword_type=keyword_type)
            session.add(kw)
            session.commit()
            session.refresh(kw)
            logger.info(f"Added keyword: {keyword} (type: {keyword_type})")
            return kw
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding keyword: {e}")
            raise
        finally:
            session.close()
    
    def get_global_keywords(self) -> List[Keyword]:
        """获取全局关键词"""
        session = self.get_session()
        try:
            return session.query(Keyword).filter(Keyword.feed_id == None).all()
        finally:
            session.close()
    
    def get_feed_keywords(self, feed_id: int) -> List[Keyword]:
        """获取指定RSS源的关键词"""
        session = self.get_session()
        try:
            return session.query(Keyword).filter(Keyword.feed_id == feed_id).all()
        finally:
            session.close()
    
    def get_all_keywords(self) -> List[Keyword]:
        """获取所有关键词"""
        session = self.get_session()
        try:
            return session.query(Keyword).all()
        finally:
            session.close()
    
    def delete_keyword(self, keyword_id: int):
        """删除关键词"""
        session = self.get_session()
        try:
            kw = session.query(Keyword).filter(Keyword.id == keyword_id).first()
            if kw:
                session.delete(kw)
                session.commit()
        finally:
            session.close()
    
    # ============ SentItem 操作 ============
    
    def is_sent(self, item_hash: str) -> bool:
        """检查是否已发送"""
        session = self.get_session()
        try:
            return session.query(SentItem).filter(SentItem.item_hash == item_hash).first() is not None
        finally:
            session.close()
    
    def mark_sent(self, feed_id: int, title: str, url: str):
        """标记为已发送"""
        session = self.get_session()
        try:
            item_hash = hashlib.sha256(f"{feed_id}:{url}".encode()).hexdigest()
            item = SentItem(item_hash=item_hash, feed_id=feed_id, title=title, url=url)
            session.add(item)
            session.commit()
        finally:
            session.close()
    
    def clean_old_sent_items(self, days: int = 7):
        """清理旧的发送记录"""
        session = self.get_session()
        try:
            cutoff = datetime.now() - timedelta(days=days)
            session.query(SentItem).filter(SentItem.sent_at < cutoff).delete()
            session.commit()
            logger.info(f"Cleaned sent items older than {days} days")
        finally:
            session.close()
    
    # ============ UserSettings 操作 ============
    
    def get_user_settings(self, user_id: int) -> UserSettings:
        """获取用户设置"""
        session = self.get_session()
        try:
            settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if not settings:
                settings = UserSettings(user_id=user_id)
                session.add(settings)
                session.commit()
                session.refresh(settings)
            return settings
        finally:
            session.close()
    
    def update_user_settings(self, user_id: int, **kwargs):
        """更新用户设置"""
        session = self.get_session()
        try:
            settings = self.get_user_settings(user_id)
            for key, value in kwargs.items():
                setattr(settings, key, value)
            session.commit()
        finally:
            session.close()


# 全局数据库实例
db = Database()
