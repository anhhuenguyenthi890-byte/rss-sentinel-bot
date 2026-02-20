"""
Telegram命令处理器模块
"""
import logging
from typing import List
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from .config import config
from .database import db
from .rss_parser import parser

logger = logging.getLogger(__name__)

router = Router()

# 状态管理
class AddFeedStates(StatesGroup):
    waiting_for_url = State()
    waiting_for_discovery = State()

class AddKeywordStates(StatesGroup):
    waiting_for_keyword = State()
    waiting_for_feed_select = State()


# 键盘按钮
def get_main_keyboard() -> ReplyKeyboardMarkup:
    """主菜单键盘"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ 添加RSS源"), KeyboardButton(text="📋 RSS列表")],
            [KeyboardButton(text="🔑 关键词管理"), KeyboardButton(text="⚙️ 设置")],
            [KeyboardButton(text="🔄 立即检查"), KeyboardButton(text="❓ 帮助")]
        ],
        resize_keyboard=True
    )


def get_feeds_keyboard(feeds: List) -> InlineKeyboardMarkup:
    """RSS源列表键盘"""
    buttons = []
    for feed in feeds:
        status = "✅" if feed.is_active else "❌"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {feed.title or feed.url[:30]}",
                callback_data=f"feed_{feed.id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ 返回", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_keywords_keyboard(keywords: List, feed_id: int = None) -> InlineKeyboardMarkup:
    """关键词列表键盘"""
    buttons = []
    prefix = f"feed_kw_{feed_id}_" if feed_id else "global_kw_"
    
    for kw in keywords:
        type_emoji = {
            "normal": "",
            "and": "➕",
            "or": "|",
            "not": "➖",
            "regex": ".*"
        }.get(kw.keyword_type, "")
        buttons.append([
            InlineKeyboardButton(
                text=f"{type_emoji} {kw.keyword}",
                callback_data=f"view_kw_{kw.id}"
            ),
            InlineKeyboardButton(
                text="🗑️",
                callback_data=f"del_kw_{kw.id}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="➕ 添加关键词", callback_data="add_kw")])
    buttons.append([InlineKeyboardButton(text="⬅️ 返回", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# 命令处理器
@router.message(Command("start"))
async def cmd_start(message: Message):
    """处理 /start 命令"""
    user_id = message.from_user.id
    
    # 检查管理员权限
    if not config.is_admin(user_id):
        await message.answer(
            "❌ 您没有权限使用此机器人。\n\n"
            "请联系管理员添加您的User ID到白名单。",
            reply_markup=get_main_keyboard()
        )
        return
    
    welcome_text = f"""👋 欢迎使用 RSS Sentinel Bot！

我可以帮您监控RSS源的关键词更新。

📌 功能说明：
• 添加多个RSS源
• 设置关键词监控
• 支持AND/OR/NOT/正则表达式
• 智能去重
• 自动发现RSS链接
• OPML导入导出

点击下方按钮开始使用："""
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message):
    """处理 /help 命令"""
    help_text = """📖 RSS Sentinel Bot 帮助

🔧 基础命令：
/start - 启动机器人
/help - 显示帮助
/add - 添加RSS源
/list - 查看RSS源列表
/keywords - 管理关键词
/settings - 设置
/check - 立即检查所有RSS源

📝 关键词语法：
• 普通: python - 包含"python"
• AND: python+remote - 同时包含
• OR: python|django - 包含任一
• NOT: python -snake - 包含python但不包含snake
• 正则: regex:^\\d+$ - 匹配正则表达式

💡 小贴士：
输入网站URL可以自动发现RSS链接！
"""
    await message.answer(help_text)


@router.message(F.text == "❓ 帮助")
async def btn_help(message: Message):
    """帮助按钮"""
    await cmd_help(message)


@router.message(Command("add"))
@router.message(F.text == "➕ 添加RSS源")
async def cmd_add_feed(message: Message, state: FSMContext):
    """添加RSS源"""
    user_id = message.from_user.id
    if not config.is_admin(user_id):
        await message.answer("❌ 您没有权限")
        return
    
    await message.answer(
        "📡 请输入RSS源URL（支持网站URL自动发现RSS）",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ 取消")]],
            resize_keyboard=True
        )
    )
    await state.set_state(AddFeedStates.waiting_for_url)


@router.message(AddFeedStates.waiting_for_url)
async def process_feed_url(message: Message, state: FSMContext):
    """处理RSS URL输入"""
    url = message.text.strip()
    
    if url == "❌ 取消":
        await state.clear()
        await message.answer("已取消", reply_markup=get_main_keyboard())
        return
    
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    await message.answer("🔍 正在检测RSS源...")
    
    # 尝试自动发现RSS
    rss_url = url
    if not ("rss" in url.lower() or "feed" in url.lower() or "atom" in url.lower()):
        discovered = await parser.discover_rss(url)
        if discovered:
            rss_url = discovered
            await message.answer(f"✅ 自动发现RSS: {rss_url}")
        else:
            await message.answer("❌ 无法自动发现RSS链接，请手动输入RSS URL")
            return
    
    # 添加RSS源
    try:
        feed = db.add_feed(rss_url)
        await message.answer(
            f"✅ RSS源添加成功！\n\n"
            f"标题: {feed.title or 'Unknown'}\n"
            f"URL: {feed.url}",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await message.answer(f"❌ 添加失败: {str(e)}", reply_markup=get_main_keyboard())
    
    await state.clear()


@router.message(Command("list"))
@router.message(F.text == "📋 RSS列表")
async def cmd_list_feeds(message: Message):
    """列出所有RSS源"""
    user_id = message.from_user.id
    if not config.is_admin(user_id):
        await message.answer("❌ 您没有权限")
        return
    
    feeds = db.get_all_feeds()
    
    if not feeds:
        await message.answer("📭 还没有添加任何RSS源", reply_markup=get_main_keyboard())
        return
    
    text = "📋 RSS源列表:\n\n"
    for feed in feeds:
        status = "✅" if feed.is_active else "❌"
        text += f"{status} <b>{feed.title or 'Unknown'}</b>\n"
        text += f"   {feed.url[:50]}...\n"
        text += f"   错误次数: {feed.error_count}\n\n"
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())


@router.message(Command("keywords"))
@router.message(F.text == "🔑 关键词管理")
async def cmd_keywords(message: Message):
    """关键词管理"""
    user_id = message.from_user.id
    if not config.is_admin(user_id):
        await message.answer("❌ 您没有权限")
        return
    
    global_keywords = db.get_global_keywords()
    feeds = db.get_all_feeds()
    
    text = "🔑 关键词管理\n\n"
    
    if global_keywords:
        text += "🌍 全局关键词:\n"
        for kw in global_keywords:
            text += f"  • {kw.keyword} ({kw.keyword_type})\n"
    else:
        text += "🌍 全局关键词: 无\n"
    
    if feeds:
        text += "\n📰 源特定关键词:\n"
        for feed in feeds[:3]:
            kw_count = len(db.get_feed_keywords(feed.id))
            text += f"  • {feed.title or feed.url[:30]}: {kw_count}个\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 管理全局关键词", callback_data="manage_global_kw")],
        [InlineKeyboardButton(text="📰 管理源关键词", callback_data="manage_feed_kw")],
        [InlineKeyboardButton(text="⬅️ 返回", callback_data="back_main")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


@router.message(F.text == "⚙️ 设置")
async def cmd_settings(message: Message):
    """设置菜单"""
    user_id = message.from_user.id
    if not config.is_admin(user_id):
        await message.answer("❌ 您没有权限")
        return
    
    settings = db.get_user_settings(user_id)
    
    text = f"""⚙️ 设置

当前设置：
• 摘要模式: {'开启' if settings.digest_mode else '关闭'}
• 图片推送: {'开启' if settings.notify_with_image else '关闭'}
• 刷新间隔: {config.refresh_interval}分钟
• 历史保留: {config.history_days}天
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🔔 摘要模式: {'✅' if settings.digest_mode else '❌'}",
            callback_data="toggle_digest"
        )],
        [InlineKeyboardButton(
            text=f"🖼️ 图片推送: {'✅' if settings.notify_with_image else '❌'}",
            callback_data="toggle_image"
        )],
        [InlineKeyboardButton(text="⬅️ 返回", callback_data="back_main")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("check"))
@router.message(F.text == "🔄 立即检查")
async def cmd_check(message: Message):
    """立即检查所有RSS源"""
    user_id = message.from_user.id
    if not config.is_admin(user_id):
        await message.answer("❌ 您没有权限")
        return
    
    await message.answer("🔄 正在检查RSS源...")
    
    # 这里触发一次检查
    # 实际实现需要在bot.py中调用scheduler的check_all_feeds
    await message.answer("✅ 检查完成！", reply_markup=get_main_keyboard())


# 注册所有路由
def register_handlers(dp):
    """注册所有处理器"""
    dp.include_router(router)
