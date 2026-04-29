# inkagent 用户手册

## 目录

1. [快速开始](#1-快速开始)
2. [选择 LLM 提供商](#2-选择-llm-提供商)
3. [记忆系统](#3-记忆系统)
4. [Telegram 机器人](#4-telegram-机器人)
4.5. [WhatsApp 机器人](#45-whatsapp-机器人)
5. [Web 搜索](#5-web-搜索)
6. [Gmail 集成](#6-gmail-集成)
7. [定时任务与心跳检查](#7-定时任务与心跳检查)
8. [自定义技能](#8-自定义技能)
9. [会话控制](#9-会话控制)
10. [完整环境变量参考](#10-完整环境变量参考)

---

## 1. 快速开始

用最少的配置把 inkagent 跑起来。

### 前置条件

- Python 3.11+
- 一个 LLM API key（Anthropic 或 OpenAI），或者一个 ChatGPT Plus/Pro 订阅

### 安装

```bash
git clone https://github.com/dengfeng-ai/inkagent
cd inkagent
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 最简配置

```bash
cp .env.example .env
```

编辑 `.env`，取消注释并填入你的 API key：

```bash
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### 启动

```bash
python -m inkagent
```

看到提示符后输入消息即可开始对话。agent 会自动使用工具、管理记忆。

### Docker 方式（推荐）

Docker 更安全 — `run_shell` 工具在容器内执行，不会影响宿主机。

```bash
docker build -t inkagent .

# CLI 模式
docker run -it --env-file .env \
  -v $(pwd)/memory:/app/memory \
  -v $(pwd)/conversations:/app/conversations \
  inkagent

# Telegram 机器人模式
docker run --env-file .env \
  -v $(pwd)/memory:/app/memory \
  -v $(pwd)/conversations:/app/conversations \
  inkagent python -m inkagent.bot

# WhatsApp 机器人模式（镜像里也要装 libmagic，详见 4.5 节）
docker run -it --env-file .env \
  -v $(pwd)/memory:/app/memory \
  -v $(pwd)/conversations:/app/conversations \
  inkagent python -m inkagent.whatsapp_bot
```

挂载 `memory/` 和 `conversations/` 目录，数据在容器重启后不会丢失。

### 文件安全

在项目目录内，agent 只能写入 `memory/` 和 `conversations/`。项目中的其他文件（源代码、配置、skills 等）对 agent 是只读的。项目目录外的文件不受限制。

这在 `write_file` 和 `edit_file` 工具层面做了硬限制。`run_shell` 工具没有硬限制，但系统提示中要求 agent 不通过它绕过写入限制。

### 验证

启动后输入 `你好` 或任意消息，agent 正常回复即表示配置成功。

---

## 2. 选择 LLM 提供商

inkagent 支持三种 LLM 提供商，通过 `.env` 中的 `LLM_PROVIDER` 切换。

### 方式 A：Anthropic

需要 Anthropic API key。

```bash
ANTHROPIC_API_KEY=sk-ant-xxxxx
LLM_PROVIDER=anthropic
```

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `ANTHROPIC_API_KEY` | — | API key（必填） |
| `LLM_MODEL` | `claude-opus-4-6` | 主模型 |
| `LLM_SMALL_MODEL` | `claude-sonnet-4-6` | 小模型（用于压缩和记忆提升） |

### 方式 B：OpenAI

需要 OpenAI API key。

```bash
OPENAI_API_KEY=sk-xxxxx
LLM_PROVIDER=openai
```

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `OPENAI_API_KEY` | — | API key（必填） |
| `LLM_MODEL` | `gpt-5.4` | 主模型 |
| `LLM_SMALL_MODEL` | `gpt-5.4-mini` | 小模型 |

### 方式 C：ChatGPT 订阅（Codex OAuth）

用 ChatGPT Plus/Pro 订阅运行，无需 API key，不产生额外费用。

**第一步：登录授权（一次性）**

```bash
python -m inkagent.codex_auth
```

浏览器会自动打开 OpenAI 授权页面。授权后 token 保存在 `~/.inkagent/codex-auth.json`，之后自动刷新。

**第二步：配置 `.env`**

```bash
LLM_PROVIDER=openai-codex
```

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `LLM_MODEL` | `gpt-5.4` | 主模型 |
| `LLM_SMALL_MODEL` | `gpt-5.4-mini` | 小模型 |

**查看登录状态：**

```bash
python -m inkagent.codex_auth status
```

**注意：** Codex 模式受 ChatGPT 订阅用量限制；不支持 embedding，记忆搜索仍需设置 `OPENAI_API_KEY`。

### 提供商功能对比

| 功能 | Anthropic | OpenAI | Codex |
|------|-----------|--------|-------|
| 需要 API key | 是 | 是 | 否 |
| 按量付费 | 是 | 是 | 否（订阅制） |
| 记忆搜索 | 需额外设 `OPENAI_API_KEY` | 自动可用 | 需额外设 `OPENAI_API_KEY` |
| 工具调用 | 支持 | 支持 | 支持 |

---

## 3. 记忆系统

inkagent 的记忆全部存储在 `memory/` 目录下的 Markdown 文件中，你可以随时查看。建议通过对话让 agent 来修改，而不是直接编辑文件。

### 记忆文件

| 文件 | 用途 | 如何更新 |
|------|------|----------|
| `IDENTITY.md` | agent 身份 — 名字、物种、语气、emoji、头像 | 对话中告诉 agent "你叫小墨" 等 |
| `SOUL.md` | agent 行为规则 — 语气、边界、核心信念 | 对话中告诉 agent "用中文回复" 等 |
| `USER.md` | 用户资料 — 姓名、角色、兴趣 | agent 在对话中自动学习 |
| `MEMORY.md` | 长期记忆 — 重要的事实和决策（首次访问时自动创建带标题模板） | `save_memory` 工具 + 自动提升 |
| `daily/YYYY-MM-DD.md` | 每日日志 — 临时笔记，一天一个文件 | `log_daily` 工具 |
| `memory.db` | 向量索引（记忆搜索用） | 自动管理 |

### 记忆的生命周期

```
对话中的信息
  ↓ log_daily
每日日志 (daily/YYYY-MM-DD.md)
  ↓ 次日自动提升
长期记忆 (MEMORY.md)
```

1. 对话过程中，agent 用 `log_daily` 将值得记录的内容写入当日日志
2. 用户说"记住这个"时，agent 用 `save_memory` 直接写入长期记忆
3. 每天首次对话时，系统自动审查昨日日志，将有价值的内容提升到 `MEMORY.md`

### 记忆搜索

记忆搜索使用 OpenAI embedding 将每日日志嵌入向量索引（`memory.db`），agent 的 `recall_memory` 工具通过向量相似度搜索日志。这意味着即使你使用 Anthropic 或 Codex 作为 LLM 提供商，记忆搜索仍需要单独设置 `OPENAI_API_KEY`：

```bash
OPENAI_API_KEY=sk-xxxxx
```

没有 `OPENAI_API_KEY` 时，记忆搜索退化为关键词匹配，基础功能不受影响。

**注意：** `MEMORY.md` 不参与搜索 — 它的内容已经直接注入到 agent 的系统提示中，agent 每次对话都能看到。

### 定制 agent 人格

直接在对话中告诉 agent 即可：

- "你叫小墨" → 更新 `IDENTITY.md`
- "用中文和我对话" → 更新 `SOUL.md`
- "我叫登峰，是 AI 工程师" → 更新 `USER.md`

建议通过对话让 agent 自行更新，保持格式一致。

---

## 4. Telegram 机器人

通过 Telegram 和 agent 对话，支持随时随地使用。

### 前置条件

- 一个已配置好的 LLM 提供商（参见[第 2 节](#2-选择-llm-提供商)）
- Telegram 账号

### 配置步骤

**第一步：创建 Telegram Bot**

1. 在 Telegram 中找到 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot`，按提示设置名称
3. 记下返回的 bot token（格式：`123456:ABC-DEF...`）

**第二步：获取你的用户 ID**

1. 在 Telegram 中找到 [@userinfobot](https://t.me/userinfobot)
2. 发送任意消息，它会返回你的数字 ID

**第三步：配置 `.env`**

```bash
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_OWNER_ID=987654321
```

**第四步：启动**

```bash
python -m inkagent.bot
```

### 验证

在 Telegram 中向你的 bot 发送任意消息，收到回复即表示成功。

### Bot 命令

| 命令 | 说明 |
|------|------|
| `/start` | 确认 bot 在线 |
| `/new` | 归档当前对话，开始新会话 |
| `/compact` | 压缩对话历史（上下文过长时使用） |

### 注意事项

- 只有 `TELEGRAM_OWNER_ID` 对应的用户能与 bot 交互（安全限制）
- 在 Telegram 模式下，定时任务（cron）自动启动，触发的消息会发送到对应的 chat
- 单条消息上限 4096 字符，超长回复会自动拆分

---

## 4.5 WhatsApp 机器人

通过 WhatsApp 跟 agent 对话——手机、网页、桌面端都能用。

底层走非官方 WhatsApp Web 协议（`neonize` → `whatsmeow`），**不需要 Meta Business 注册，不需要公网 webhook，不需要审批消息模板**。bot 作为 Linked Device 配对到你控制的某个 WhatsApp 账号上。

### 前置条件

- 一个已配置好的 LLM 提供商（参见[第 2 节](#2-选择-llm-提供商)）
- **一个专门给 bot 用的 WhatsApp 副号**（强烈建议——见下方"关于 bot 账号"）
- 宿主机装了 `libmagic`

### 配置步骤

**第一步：安装 libmagic**

```bash
brew install libmagic                  # macOS
sudo apt install libmagic1             # Debian / Ubuntu
```

`neonize` 启动时通过 dlopen 加载 `libmagic`，没装会 import 失败。

**第二步：配置 `.env`**

```bash
# 你**主号**手机号（你给 bot 发消息时用的那个号），纯数字 + 国码，无 '+'
# 例如：6591234567（新加坡 +65 91234567）
WHATSAPP_OWNER_PHONE=6591234567
```

**第三步：启动并配对**

```bash
python -m inkagent.whatsapp_bot
```

终端会打印一个 QR 码。在 **bot 副号那台手机上**（不是你主号）：

1. 打开 WhatsApp → **Linked Devices**（已链接的设备）
2. 点击 **Link a device**（链接设备）
3. 扫描终端里的 QR

约 5–10 秒后会看到 `WhatsApp bot connected. Owner phone: ...`。配对状态保存在 `memory/whatsapp_session.db`，下次启动直接复用（不用再扫码）。

### 验证

从你**主号**给 bot 副号发条 `hi`，bot 几秒内回复即说明成功。

### Bot 命令

| 命令 | 说明 |
|------|------|
| `/new` | 归档当前对话，开始新会话 |
| `/compact` | 压缩对话历史 |

### 关于 bot 账号

bot 作为 Linked Device 挂在**一个** WhatsApp 账号上，那个账号收到的所有消息它都看得到。三个用副号而不是主号的理由：

1. **跟自己聊天体验差。** WhatsApp 没有 `@inkagent_bot` 这种独立 bot 实体——要"跟 bot 对话"就得有两端。如果 bot 就是你主号，你只能用"跟自己聊天"功能，发问和回答都显示成"me"。
2. **bot 看见你所有聊天。** 配对到主号后，任何人发给你的消息都会进 bot 的事件流。
3. **bot 以你的身份发消息。** agent 任何 bug / 提示注入都可能让 bot 替你给真人发消息。

副号方案：双卡手机、WhatsApp Business app（可与普通 WhatsApp 在同一台手机并存）、虚拟号码都行。

### 已知问题："AI from Meta" 隐私横幅

主号给 bot 发消息时，WhatsApp 客户端会在每条消息上方显示类似 *"AI from Meta receives messages to improve AI quality and generate messages for this business"* 的横幅，bot 的每条回复也会带 "AI ✦" 标签。**这个无法去除**——WhatsApp 的分类器会把任何"非手机 app + 自动化回复模式"的 linked device 标记为 AI/business 客户端，即使副号本身是普通（非 Business）账号。

横幅本身有点误导：端到端加密照旧（whatsmeow 直连 WhatsApp 服务端，Meta 看到的是密文），bot 跑在你自己机器上没经过 Meta AI。这只是 WhatsApp 对所有第三方 client 的通用 UI 警告。

### 注意事项

- 只有发送方手机号匹配 `WHATSAPP_OWNER_PHONE` 的消息会被处理；其他人发的消息静默丢弃
- 已处理 LID 寻址——WhatsApp 用 LID 模式发消息时，bot 会从 `SenderAlt` 里取真正的手机号 JID 来做 owner 校验
- WhatsApp 模式下定时任务自动启动，但只投递 session ID 以 `wa_` 开头的任务；如果同时跑 Telegram bot，两边各管各的（`tg_*` / `wa_*`）
- 跑 agent 时显示 "正在输入..." 指示器（每 10 秒刷新一次）
- 单条消息上限 4096 字符，超长回复自动拆分

---

## 5. Web 搜索

让 agent 具备搜索互联网的能力。

### 前置条件

- Brave Search API key（免费额度：2000 次/月）

### 配置步骤

**第一步：获取 API key**

1. 访问 [Brave Search API](https://brave.com/search/api/)
2. 注册并创建一个 API key

**第二步：配置 `.env`**

```bash
BRAVE_API_KEY=BSA-xxxxx
```

### 验证

启动后告诉 agent "搜索一下今天的新闻"。agent 会调用 `web_search` 工具并返回结果。

### 相关工具

| 工具 | 说明 |
|------|------|
| `web_search` | 搜索 Brave，返回标题、摘要、链接（默认 5 条，最多 20 条） |
| `web_fetch` | 抓取网页 URL，提取正文内容（15 秒超时） |

`web_fetch` 无需额外配置，可直接使用。

---

## 6. Gmail 集成

让 agent 搜索、阅读和发送 Gmail 邮件。

### 前置条件

- Gmail 账号
- 已开启两步验证

### 配置步骤

**第一步：生成 App Password**

1. 访问 [Google App Passwords](https://myaccount.google.com/apppasswords)（需先开启两步验证）
2. 应用名称填 `inkagent`（或任意名称）
3. 记下生成的 16 位密码（格式：`xxxx xxxx xxxx xxxx`）

**第二步：配置 `.env`**

```bash
GMAIL_ADDRESS=your@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

### 验证

启动后告诉 agent "查一下最近的未读邮件"。agent 会调用 `gmail_search` 工具。

### 相关工具

| 工具 | 说明 |
|------|------|
| `gmail_search` | 搜索邮件（IMAP 搜索语法），返回发件人、主题、日期 |
| `gmail_read` | 读取完整邮件内容（包括附件列表） |
| `gmail_send` | 发送或回复邮件（支持 `In-Reply-To` 线程回复） |
| `gmail_mark_read` | 批量标记邮件为已读 |

### IMAP 搜索语法示例

| 语法 | 说明 |
|------|------|
| `UNSEEN` | 未读邮件 |
| `FROM alice` | 来自 alice 的邮件 |
| `SUBJECT invoice` | 主题包含 invoice |
| `SINCE 01-Jan-2026` | 指定日期之后的邮件 |
| `SUBJECT invoice UNSEEN` | 可组合使用 |

### 注意事项

- 使用的是 App Password 而不是 Gmail 密码
- App Password 需要 Gmail 开启两步验证后才能生成
- 邮件操作通过 IMAP（读取）和 SMTP（发送）协议，不是 Gmail API

---

## 7. 定时任务与心跳检查

让 agent 按时间表自动执行任务，主动通知你。

### 前置条件

- Telegram 或 WhatsApp 机器人模式（定时任务需要常驻进程；CLI 模式下可创建任务，但需要某个 bot 运行时才触发）

### 使用方法

在对话中直接告诉 agent 即可：

```
你> 每天早上 9 点给我发一份天气和邮件摘要
你> 每周一 10 点提醒我写周报
你> 取消那个天气任务
```

agent 会自动调用 `create_cron` / `list_crons` / `delete_cron` 工具。

### Cron 表达式参考

| 表达式 | 含义 |
|--------|------|
| `0 9 * * *` | 每天 9:00 |
| `0 9 * * 1-5` | 工作日 9:00 |
| `*/30 * * * *` | 每 30 分钟 |
| `0 10 * * 1` | 每周一 10:00 |
| `0 9,18 * * *` | 每天 9:00 和 18:00 |

格式：`分 时 日 月 周几`

默认时区为 `Asia/Shanghai`，可在创建时指定其他 IANA 时区。

### 心跳检查（Heartbeat）

心跳是一种特殊的定时任务：定期运行后台检查（邮件、日历等），只在有事时通知你，没事时保持安静。

**配置步骤：**

**第一步：编辑检查清单**

创建或编辑 `memory/HEARTBEAT.md`，列出你想让 agent 定期检查的内容：

```markdown
## 检查项

- [ ] 查看未读邮件，如果有重要的就通知我
- [ ] 检查日历看今天有没有即将开始的会议
```

**第二步：创建心跳任务**

在对话中告诉 agent：

```
你> 创建一个心跳任务，每 30 分钟检查一次
```

agent 会创建一个 `silent_ok=true` 的 cron 任务。当没有需要注意的事项时，agent 回复 `HEARTBEAT_OK`，通知会被静默吞掉。

**第三步：验证**

```
你> 列出所有定时任务
```

确认心跳任务已创建。

### 注意事项

- 每个定时任务绑定创建时的会话（Telegram chat 或 WhatsApp 主号），触发后消息发到同一个 chat。每个 bot 的 scheduler 只投递自己前缀的任务（`tg_*` / `wa_*`）
- 每次触发使用独立会话（带时间戳的 session ID），不会干扰正在进行的对话
- 心跳的安静时段为 23:00-08:00（在 `skills/heartbeat/SKILL.md` 中定义），安静时段只通知紧急事项

---

## 8. 自定义技能

通过 Markdown 文件教 agent 新的工作流程，不需要写代码。技能指导 agent 如何组合现有工具完成特定任务。

所有技能都放在 `skills/` 下，在编辑器里直接修改即可——agent 自身不修改技能文件。

### 创建新技能

在 `skills/` 下创建目录和 `SKILL.md` 文件：

```
skills/
└── daily_report/
    └── SKILL.md
```

编写 `SKILL.md`：

```yaml
---
name: daily_report
description: 生成当日工作总结
---

当用户要求生成日报时：

1. 使用 `recall_memory` 搜索今天的日志
2. 将内容分组为：决策、待办、讨论话题、备注
3. 用 Markdown 格式输出总结
```

放好文件后，agent 下次启动自动发现。agent 在系统提示中看到技能名称和描述，需要时用 `read_file` 加载完整指令。

### 修改已有技能

直接在编辑器中打开对应的 `skills/<name>/SKILL.md` 修改即可，agent 下次启动生效。

### 条件加载

可以在 frontmatter 中用 `requires` 指定前置条件。不满足时技能会被静默跳过：

```yaml
---
name: audio_transcribe
description: 转录音频文件
requires:
  env: [OPENAI_API_KEY]       # 需要设置的环境变量
  bins: [ffmpeg]              # 需要安装的命令行工具
---
```

### 自带技能

仓库在 `skills/` 下自带一个技能：

| 技能 | 说明 |
|------|------|
| `heartbeat` | 定期后台检查工作流（配合 cron 使用） |

---

## 9. 会话控制

### CLI 模式

| 命令 | 说明 |
|------|------|
| `/new` | 归档当前对话，开始新会话 |
| `/compact` | 压缩对话历史（将旧消息总结为摘要，保留最近 3 轮） |
| `quit` 或 `exit` | 退出 |

### Telegram 模式

| 命令 | 说明 |
|------|------|
| `/start` | 确认 bot 在线 |
| `/new` | 归档当前对话，开始新会话 |
| `/compact` | 压缩对话历史 |

### WhatsApp 模式

| 命令 | 说明 |
|------|------|
| `/new` | 归档当前对话，开始新会话 |
| `/compact` | 压缩对话历史 |

### 何时使用 `/compact`

当对话很长、agent 响应变慢或接近上下文窗口限制时使用。系统也会在上下文达到 80%（约 160k tokens）时自动触发压缩。

### 对话持久化

对话历史自动保存在 `conversations/` 目录下（JSON 格式）。使用 `/new` 后，旧对话被归档，新对话从空白开始（但记忆文件保持不变）。

---

## 10. 完整环境变量参考

以下是所有环境变量的汇总。完整的模板参见项目根目录的 `.env.example`。

### LLM 提供商

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `LLM_PROVIDER` | 否 | `anthropic` | `anthropic`、`openai` 或 `openai-codex` |
| `LLM_MODEL` | 否 | 因提供商而异 | 主模型名称 |
| `LLM_SMALL_MODEL` | 否 | 因提供商而异 | 小模型（压缩/记忆提升用） |
| `ANTHROPIC_API_KEY` | Anthropic 必填 | — | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI 必填 | — | OpenAI API key |

### 记忆搜索

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `OPENAI_API_KEY` | 否 | — | 用于 embedding 的记忆搜索（即使 LLM 用 Anthropic/Codex 也需要设置；不设则退化为关键词匹配） |

### Telegram

| 变量 | 必填 | 说明 |
|------|------|------|
| `TELEGRAM_BOT_TOKEN` | bot 模式必填 | BotFather 提供的 token |
| `TELEGRAM_OWNER_ID` | bot 模式必填 | 你的 Telegram 数字用户 ID |

### WhatsApp

| 变量 | 必填 | 说明 |
|------|------|------|
| `WHATSAPP_OWNER_PHONE` | WhatsApp bot 模式必填 | 你的手机号（纯数字 + 国码，无 `+`，例如 `6591234567`）。bot 只接受这个号发来的消息；首次启动需扫码把 bot 配对到**另一个** WhatsApp 账号。 |

### Web 搜索

| 变量 | 必填 | 说明 |
|------|------|------|
| `BRAVE_API_KEY` | web_search 必填 | [Brave Search API](https://brave.com/search/api/) key |

### Gmail

| 变量 | 必填 | 说明 |
|------|------|------|
| `GMAIL_ADDRESS` | Gmail 必填 | Gmail 邮箱地址 |
| `GMAIL_APP_PASSWORD` | Gmail 必填 | [App Password](https://myaccount.google.com/apppasswords)（需开启两步验证） |

### 可观测性（可选）

Langfuse 追踪 — `pip install -e ".[langfuse]"`

| 变量 | 必填 | 说明 |
|------|------|------|
| `LANGFUSE_PUBLIC_KEY` | 否 | [Langfuse](https://langfuse.com) 公钥 |
| `LANGFUSE_SECRET_KEY` | 否 | Langfuse 密钥 |
| `LANGFUSE_HOST` | 否 | Langfuse 服务地址（默认：`https://cloud.langfuse.com`） |

设置了 `LANGFUSE_PUBLIC_KEY` 且安装了 `langfuse` 包时自动启用，否则所有追踪调用退化为 no-op。
