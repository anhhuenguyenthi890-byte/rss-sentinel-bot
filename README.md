# RSS Sentinel Bot

Smart RSS Keyword Monitoring Bot for Telegram

## 功能简介

一个强大的RSS关键词监控Telegram Bot，支持以下功能：

- 多RSS源管理
- 多关键词监控（支持 AND/OR/NOT/正则表达式）
- 智能去重
- RSS自动发现
- 健康检查
- OPML导入导出
- 摘要模式
- 媒体解析
- 异步架构

## 快速开始

### 一键部署

#### 使用 Docker Compose (推荐)

```bash
# 1. 克隆仓库
git clone https://github.com/anhhuenguyenthi890-byte/rss-sentinel-bot.git
cd rss-sentinel-bot

# 2. 复制配置文件
cp .env.example .env

# 3. 编辑配置文件，填入你的 Telegram Bot Token
nano .env

# 4. 启动容器
docker-compose up -d
```

#### Railway 一键部署

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/anhhuenguyenthi890-byte/rss-sentinel-bot)

#### Heroku 一键部署

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

### 本地开发

```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\\Scripts\\activate  # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 复制配置
cp .env.example .env

# 4. 编辑配置
nano .env

# 5. 运行机器人
python -m src.bot
```

## 配置说明

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| TELEGRAM_BOT_TOKEN | Telegram Bot Token | (必填) |
| ADMIN_USER_IDS | 管理员User ID，多个用逗号分隔 | 空 |
| REFRESH_INTERVAL | RSS刷新间隔(分钟) | 10 |
| DIGEST_MODE | 每日摘要模式 | false |
| DATABASE_URL | 数据库连接字符串 | sqlite:///bot.db |
| LOG_LEVEL | 日志级别 | INFO |
| HISTORY_DAYS | 历史记录保留天数 | 7 |

## 使用方法

### 基础命令

- `/start` - 启动机器人，显示主菜单
- `/add` - 添加新的RSS源
- `/list` - 查看所有订阅的RSS源
- `/keywords` - 管理监控关键词
- `/settings` - 配置设置
- `/opml` - 导入/导出RSS源
- `/help` - 帮助指南

### 关键词语法

- **AND 逻辑**: `python + remote` - 必须同时包含
- **OR 逻辑**: `python | django` - 包含任一即可
- **NOT 逻辑**: `python -snake` - 必须不包含
- **正则表达式**: `regex:^\\d+$` - 匹配正则

## 功能特性

### 智能关键词
- 支持全局关键词（应用于所有RSS源）
- 支持源特定关键词（仅应用于指定RSS源）
- 支持复杂的组合逻辑

### RSS管理
- 自动发现RSS链接
- 健康检查和自动禁用失效源
- OPML批量导入导出

### 消息优化
- 精美格式化消息
- 支持图片预览
- Telegram Instant View链接
- 每日摘要模式

### 技术特性
- 异步架构，高效处理数百RSS源
- SQLite/PostgreSQL支持
- Docker容器化部署
- 健康检查和自动重启

## 技术栈

- Python 3.11+
- aiogram 3.x (异步Telegram框架)
- feedparser (RSS解析)
- SQLAlchemy (数据库)
- APScheduler (定时任务)
- aiohttp (异步HTTP)

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
