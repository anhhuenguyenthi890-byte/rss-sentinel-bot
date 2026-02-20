"""
RSS Sentinel Bot - 主入口
"""
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from .config import config
from .handlers import router

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    logger.info("Starting RSS Sentinel Bot...")
    
    # 验证配置
    try:
        config_check = config.telegram_bot_token
        if not config_check:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set!")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    # 创建bot和dispatcher
    bot = Bot(token=config.telegram_bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # 注册处理器
    dp.include_router(router)
    
    # 启动调度器（在bot启动后）
    from .scheduler import start_scheduler
    start_scheduler(bot)
    
    logger.info("Bot is ready!")
    
    # 开始轮询
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
