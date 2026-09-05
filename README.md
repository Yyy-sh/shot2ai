# 📸 shot2ai — 一键截图，AI 秒回解题答案

> 按一下快捷键，把屏幕上的题目发给 **企业微信机器人**，机器人调用 **视觉大模型** 读图分析，再把**答案和解析发回你的企微会话（单聊 / 群聊）**。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-0078d6)

本项目为**原生开源项目**，核心方案是用**企业微信智能机器人「长连接」模式**：本地程序通过 WebSocket 直接充当机器人，**无需公网服务器、无需回调地址、无需消息加解密**，开机即可用。

---

## 🎯 它能做什么

**面向刷题、测评练习、截图 OCR 提问等场景**，把「截题 → 提问 → 看解析」压缩到一步：

1. 🖱️ 在题目页按一下 `Ctrl+Alt+S`，拖拽框选题目区域
2. 📤 截图**自动上传到你的企微会话**（单聊或群聊）
3. 🧠 机器人调用视觉模型**分析题目**
4. 💬 几秒后**答案与简要解析出现在群聊/会话中**

```
   ⌨️ Ctrl+Alt+S 框选题目
          │
          ▼
   企微群聊收到截图 ──▶ 视觉大模型分析 ──▶ 群聊弹出答案
```

- ⚡ **快**：简单题约 2~4 秒，复杂推理题约 10 秒，实测远低于 60 秒
- 🚫 **静默截图不抢焦点**：框选时不会触发网页失焦检测
- 🔌 **模型可插拔**：任意 Anthropic 兼容的视觉模型都能接入（见下）

> ⚠️ **使用边界与免责声明**
>
> 本项目定位为**个人学习、练习、截图 OCR 提问**的辅助工具，仅供学习与研究。
> **请勿用于任何考试作弊、违反考试平台规则、或违反法律法规的场景。**
> 使用本工具产生的一切后果由使用者自行承担，作者不承担任何责任。

---

## 🔌 自定义你的模型

默认使用 **DeepSeek `deepseek-v4-flash-vision-exp`**。由于底层走 **Anthropic 兼容 Messages API**，任何支持该格式的视觉模型都**只需改 `config.json` 即可接入**，例如：

| 模型 | `base_url` | 说明 |
|---|---|---|
| DeepSeek 视觉 | `https://api.deepseek.com/anthropic` | 默认，快且准 |
| 阿里百炼 Qwen | `.../apps/anthropic`（DashScope 兼容端点） | 需百炼订阅/按量 key |
| Claude 视觉系列 | Anthropic 官方端点 | 需自行配置 |

> 模型支持「思考模式」时，可调 `reasoning_effort` 控制推理强度（`low` / `high` / `max`）。

---

## 📦 环境要求

- Windows 10 / 11
- Python 3.10+（建议 3.12）

## 🚀 安装

```bash
# 1. 克隆仓库
git clone https://github.com/Yyy-sh/shot2ai.git
cd shot2ai

# 2. （可选）创建虚拟环境
conda create -n offer-screenshot python=3.12 -y
conda activate offer-screenshot

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置（见下方「配置」）
copy config.example.json config.json   # Windows；Linux/macOS 用 cp
```

## ⚙️ 配置

复制模板并填入你的密钥：

```bash
copy config.example.json config.json
```

然后编辑 `config.json`：

| 字段 | 说明 |
|---|---|
| `model.api_key` | 视觉模型 API Key（DeepSeek 在 [platform.deepseek.com](https://platform.deepseek.com) 申请，`sk-` 开头） |
| `model.base_url` | Anthropic 兼容端点，默认 DeepSeek |
| `model.model_name` | 视觉模型名，默认 `deepseek-v4-flash-vision-exp` |
| `model.reasoning_effort` | 思考强度：`low` / `high` / `max`（`high` 快且准，`max` 更强但更慢） |
| `model.max_tokens` | 最大输出 token |
| `model.max_side` | 图片压缩长边（像素），越小越快，默认 960 |
| `wecom_bot.bot_id` | 企微智能机器人 ID |
| `wecom_bot.secret` | 企微智能机器人密钥 |
| `hotkey` | 截图快捷键，默认 `ctrl+alt+s` |
| `capture_mode` | `region` 框选 / `fullscreen` 全屏 |

> 🔒 **`config.json` 含密钥，已被 `.gitignore` 排除，切勿提交到公开仓库。**

### 获取企微机器人 bot_id / secret

1. 登录[企业微信管理后台](https://work.weixin.qq.com/) → 应用管理 → 智能机器人。
2. 创建机器人，**开启 API 模式**，连接方式选**长连接**。
3. 复制 `bot_id` 和 `secret` 填入 `config.json`。
4. 在企微里**添加机器人为联系人**（单聊），或把机器人**拉进群聊**——都能收到截图与答案。

## ▶️ 运行

```bash
conda activate offer-screenshot   # 若用 conda
python main.py
```

或直接双击 [`run.bat`](run.bat)（内置 conda activate）。

使用流程：

1. 启动后看到连接成功提示。
2. **在企微里给机器人发一条消息**（任意内容）激活会话——企微规则要求用户先发消息，机器人才可主动推送。
3. 按 `Ctrl+Alt+S`，拖拽框选屏幕上的题目区域。
4. 截图 + AI 答案会依次出现在企微会话里。

## 📁 文件结构

```
main.py              主入口：快捷键监听 + 截图编排 + 模型调用
capture.py           截图：静默全屏 + 无焦点框选（防失焦检测）
llm_client.py        视觉模型调用（Anthropic 兼容 API）
wecom_bot.py         企微智能机器人长连接客户端（WebSocket）
config.example.json  配置模板（脱敏）
requirements.txt     依赖
run.bat              Windows 一键启动（conda）
tools/check_model.py 模型连通性检查脚本
```

## ❓ 常见问题

- **没有收到机器人推送**：必须先在企微里给机器人**发一条消息**，机器人才可主动推送。
- **图片发送失败**：代码已压缩为 JPEG 且控制在 2MB 内；仍失败请缩小框选范围。
- **模型 400/401 错误**：确认 `model.api_key` 有效、`base_url` 与模型匹配。
- **模型不输出答案**：通常是截图太糊或题目过难导致思考超限；请截得更清晰、缩小范围，或调大 `max_tokens`。
- **高分屏框选偏移**：代码已做 DPI 感知；仍有问题可把 Windows 显示缩放设为 100%。
- **连接频繁断开**：程序内置 30 秒心跳 + 指数退避重连；持续失败请检查网络或 `bot_id/secret`。

## 🔧 技术要点

- **企微长连接协议**：`aibot_subscribe` 鉴权 → 30s `ping` 心跳 → `aibot_msg_callback` 收消息 → `aibot_send_msg` 主动发送；响应帧用 `headers.req_id` 关联。
- **图片上传**：`aibot_upload_media_init` → 分片 `chunk`（≤512KB）→ `finish` 拿 `media_id` → 发 `image` 消息。
- **思考模式**：`thinking: {"type": "enabled"}` + `output_config.effort`。关闭思考会导致推理题算错，务必开启。
- **防失焦截图**：先 `ImageGrab.grab()` 静默全屏截图，再弹无焦点遮罩（`WS_EX_NOACTIVATE`）框选，全程不抢焦点。

## 📄 License

[MIT](LICENSE) © 2026 Yyy-sh
