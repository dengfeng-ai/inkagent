<p align="right">
  <a href="README.md">English</a> &nbsp;·&nbsp; <b>中文</b>
</p>

<p align="center">
  <img src="assets/logo.svg" width="360" alt="inkagent"/>
</p>

<p align="center">
  <b>轻量级个人 AI Agent，本地运行，Markdown 驱动记忆。</b>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat" alt="License"></a>
  <img src="https://img.shields.io/badge/Python-%E2%89%A53.11-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Docker-lightgrey?style=flat" alt="Platform">
  <img src="https://img.shields.io/badge/LLM-Claude%20%7C%20OpenAI%20%7C%20ChatGPT-green?style=flat" alt="LLM Providers">
</p>

<p align="center">
  <a href="docs/guide-zh.md">用户手册</a> &nbsp;&middot;&nbsp;
  <a href="#为什么选-inkagent">为什么选 inkagent？</a> &nbsp;&middot;&nbsp;
  <a href="#按需配置">按需配置</a> &nbsp;&middot;&nbsp;
  <a href="#快速开始">快速开始</a> &nbsp;&middot;&nbsp;
  <a href="#路线图">路线图</a>
</p>

## 为什么选 inkagent？

- **本地运行** — 数据留在你自己的机器上，不存在别人的云里
- **Markdown 记忆** — 人设、用户档案、长期记忆、每日日志，全部是你拥有的 `.md` 文件
- **渐进式使用** — 从 CLI 聊天开始，按需添加 Telegram、网页搜索、Gmail、定时任务
- **多模型支持** — Claude、OpenAI 或 ChatGPT 订阅（无需 API Key），一个环境变量切换
- **易于扩展** — 用一个 Markdown 文件教会 Agent 新工作流，无需写代码

## 按需配置

从最简配置开始，按需逐步开启更多能力。每一级都建立在前一级的基础上。

| 级别 | 你能做什么 | 需要配置 | 指南 |
|------|-----------|---------|------|
| **从这里开始** | 在终端和 AI 对话 | 一个 API Key | [快速开始](#快速开始) |
| **移动访问** | 通过 Telegram 随时聊天 | + Telegram Bot Token | [Telegram 机器人](docs/guide-zh.md#4-telegram-机器人) |
| **联网助手** | Agent 可以搜索互联网 | + Brave API Key | [Web 搜索](docs/guide-zh.md#5-web-搜索) |
| **邮件助手** | Agent 可以读写 Gmail | + Gmail 应用专用密码 | [Gmail 集成](docs/guide-zh.md#6-gmail-集成) |
| **主动助手** | 定时任务、后台检查 | Telegram + 心跳配置 | [定时任务](docs/guide-zh.md#7-定时任务与心跳检查) |
| **更强记忆** | 对历史对话进行语义搜索 | + OpenAI API Key（用于 embedding） | [记忆搜索](docs/guide-zh.md#3-记忆系统) |

> **没有 API Key？** 设置 `LLM_PROVIDER=openai-codex` 即可使用你的 ChatGPT Plus/Pro 订阅运行。详见[模型配置指南](docs/guide-zh.md#2-选择-llm-提供商)。

## 快速开始

```bash
git clone https://github.com/dengfeng-ai/inkagent
cd inkagent
cp .env.example .env
```

编辑 `.env`，填入你的 API Key：

```bash
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### Docker（推荐）

```bash
docker build -t inkagent .
```

运行 CLI：

```bash
docker run -it --env-file .env \
  -v $(pwd)/memory:/app/memory \
  -v $(pwd)/conversations:/app/conversations \
  inkagent
```

运行 Telegram 机器人：

```bash
docker run -it --env-file .env \
  -v $(pwd)/memory:/app/memory \
  -v $(pwd)/conversations:/app/conversations \
  inkagent python -m inkagent.bot
```

### 本地运行

需要 **Python 3.11+**。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 运行 CLI
python -m inkagent

# 运行 Telegram 机器人
python -m inkagent.bot
```

Telegram 机器人、多模型配置、Gmail、网页搜索、定时任务等更多功能请参阅[用户手册](docs/guide-zh.md)。

## 工作原理

inkagent 是一个 Agent 循环：你发送消息 → LLM 决定调用哪些工具 → 工具执行 → 结果回传给 LLM → 循环直到完成。所有记忆存储为 `memory/` 目录下的 Markdown 文件，随时可以查看。

架构细节和开发信息见 [CLAUDE.md](CLAUDE.md)。

## 路线图

- [x] CLI + Shell 工具 + Markdown 记忆
- [x] LLM 可观测性（Langfuse）
- [x] Telegram 机器人
- [x] 长期记忆 + 每日日志 + 自动晋升
- [x] 文件操作工具（读、写、编辑、列目录）
- [x] 定时任务（Cron 调度器 + 工具）
- [x] 网页搜索 + 页面抓取工具
- [x] 记忆搜索（sqlite-vec + OpenAI embedding，优雅降级）
- [x] 指令技能 — 基于 Markdown 的工作流定义，与工具分离
- [x] Gmail 工具（IMAP/SMTP + App Password）
- [x] 心跳 — 定期主动检查（读取 `memory/HEARTBEAT.md` 清单，有事才通知）

## 许可证

MIT
