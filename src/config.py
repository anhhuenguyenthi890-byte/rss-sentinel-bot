"""
配置管理模块
从环境变量加载配置
"""
import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Bot configuration"""
    
    # Telegram配置
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    admin_user_ids: List[int] = field(default_factory=lambda: 
        [int(uid.strip()) for uid in os.getenv("ADMIN_USER_IDS", "").split(",") if uid.strip().isdigit()])
    
    # RSS配置
    refresh_interval: int = field(default_factory=lambda: int(os.getenv("REFRESH_INTERVAL", "10")))
    digest_mode: bool = field(default_factory=lambda: os.getenv("DIGEST_MODE", "false").lower() == "true")
    
    # 数据库配置
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///bot.db"))
    
    # 日志配置
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    
    # 历史记录配置
    history_days: int = field(default_factory=lambda: int(os.getenv("HISTORY_DAYS", "7")))
    
    def __post_init__(self):
        """验证配置"""
        if not self.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required!")
    
    @property
    def is_admin_mode(self) -> bool:
        """是否启用管理员模式"""
        return len(self.admin_user_ids) > 0
    
    def is_admin(self, user_id: int) -> bool:
        """检查用户是否是管理员"""
        if not self.is_admin_mode:
            return True  # 非管理员模式，所有用户都可以使用
        return user_id in self.admin_user_ids


# 全局配置实例
config = Config()
