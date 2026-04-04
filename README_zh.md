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
  <a href="#功能特性">功能</a> &nbsp;&middot;&nbsp;
  <a href="#快速开始">快速开始</a> &nbsp;&middot;&nbsp;
  <a href="#架构">架构</a> &nbsp;&middot;&nbsp;
  <a href="#路线图">路线图</a>
</p>

## 功能特性

- **Agent 工具循环** — 将消息发送给 LLM，执行工具，回传结果，循环直到完成
- **Markdown 记忆** — 人设、用户档案、长期记忆、每日日志，全部是可读写的 `.md` 文件
- **记忆自动晋升** — 每日日志由小模型自动筛选，精华内容晋升为长期记忆
- **记忆搜索** — 使用 sqlite-vec 对每日日志建立向量索引（需要 OpenAI API Key 做 embedding，无 Key 时回退到关键词搜索）
- **多模型支持** — 支持 Anthropic (Claude)、OpenAI、ChatGPT 订阅 (Codex OAuth)，通过环境变量切换
- **自注册工具** — Shell、文件操作、网页搜索、Gmail、定时任务等
- **指令技能** — 用一个 Markdown 文件教会 Agent 新工作流，无需写代码
- **定时任务与心跳** — 基于 cron 的调度器，支持主动通知；心跳模式用于静默后台检查
- **自动驾驶** — 自主任务队列，Agent 在每次心跳周期中自动领取、执行和归档任务
- **双界面** — CLI (`main.py`) 或 Telegram 机器人 (`bot.py`)
- **可观测性** — 可选 [Langfuse](https://langfuse.com) 追踪所有 LLM 调用和工具执行

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

docker run -it --env-file .env \
  -v $(pwd)/memory:/app/memory \
  -v $(pwd)/conversations:/app/conversations \
  -v $(pwd)/user_skills:/app/user_skills \
  inkagent
```

运行 Telegram 机器人：

```bash
docker run -it --env-file .env \
  -v $(pwd)/memory:/app/memory \
  -v $(pwd)/conversations:/app/conversations \
  -v $(pwd)/user_skills:/app/user_skills \
  inkagent python -m inkagent.bot
```

### 本地运行

需要 **Python 3.11+**。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m inkagent

# 运行 Telegram 机器人
python -m inkagent.bot
```

Telegram 机器人、多模型配置、Gmail、网页搜索、定时任务等更多功能请参阅[用户手册](docs/guide-zh.md)。

## 架构

```
项目根目录/
├── inkagent/            # Python 包
│   ├── cli.py           # CLI 入口
│   ├── bot.py           # Telegram 机器人入口
│   ├── brain.py         # Agent 循环（模型无关）
│   ├── config.py        # 共享常量
│   ├── memory.py        # Markdown 记忆（读写）
│   ├── providers/       # 可插拔 LLM 提供者
│   └── tools/           # 自注册 Python 工具
├── skills/              # 内置指令技能（Git 跟踪）
├── user_skills/         # 用户技能覆盖（gitignored）
├── memory/              # 所有记忆（gitignored）
└── pyproject.toml       # 包元数据 + 依赖
```

核心设计：`brain.py` 对具体工具和技能零感知。工具通过 `@registry.register(...)` 自注册，指令技能从 `skills/` 和 `user_skills/` 自动发现 — 添加任何一种都不需要改动核心代码。`user_skills/` 中同名技能会覆盖内置版本，`git pull` 升级不会产生冲突。

## 路线图

- [x] CLI + Shell 工具 + Markdown 记忆
- [x] Langfuse 可观测性
- [x] Telegram 机器人
- [x] 长期记忆 + 每日日志 + 自动晋升
- [x] 文件操作工具（读、写、编辑、列目录）
- [x] 定时任务（Cron 调度器 + 工具）
- [x] 网页搜索 + 页面抓取工具
- [x] 记忆搜索（sqlite-vec + OpenAI embedding，优雅降级）
- [x] 指令技能 — 基于 Markdown 的工作流定义，与工具分离
- [x] Gmail 工具（IMAP/SMTP + App Password）
- [x] 心跳 — 定期主动检查（读取 `HEARTBEAT.md` 清单，有事才通知）
- [x] 自动驾驶 — 自主任务队列，支持自动归档
- [ ] 发布到 PyPI

## 许可证

MIT
