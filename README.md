# shot2ai — 快捷键截图 → 企微机器人 → AI 视觉解题

按下快捷键框选屏幕 → 截图发到**企业微信** → 视觉大模型读图并给出答案 → 答案发回同一个企微会话。

参考 [OfferBiye](https://offerbiye.com) 的工作方式，用**企业微信智能机器人「长连接」模式**实现，本地程序通过 WebSocket 直接充当机器人，**无需公网服务器、无需回调地址、无需消息加解密**。

> ⚠️ **使用边界与免责声明**
>
> 本项目定位为**个人学习、刷题、截图 OCR 提问**的辅助工具，仅供学习与研究使用。
> **请勿将本工具用于任何考试作弊、违反考试平台规则、或违反法律法规的场景。**
> 使用本工具产生的后果由使用者自行承担，作者不承担任何责任。

## 特性

- 🖱️ **快捷键框选截图**（默认 `Ctrl+Alt+S`），拖拽框选题目区域
- 🤖 **企微长连接机器人**：截图 + 答案直接推送到你的企微会话，无需服务器
- 👁️ **视觉大模型解题**：DeepSeek `deepseek-v4-flash-vision-exp`，支持思考模式（推理强度可调）
- ⚡ **快**：简单题 2~4 秒，复杂题约 10 秒，实测远低于 60 秒
- 🚫 **静默截图不抢焦点**：避免触发网页失焦检测（见 [capture.py](capture.py)）

## 工作原理

```
企微里给机器人发条消息（激活会话）
   │  绑定会话 userid
   ▼
按快捷键 (默认 Ctrl+Alt+S)
   │  静默全屏截图（不抢焦点）→ 框选题目区域
   ▼
本地截图 (Pillow + tkinter 无焦点遮罩)
   │
   ├─▶ 企微长连接 aibot_send_msg —— 推送「截图」到会话
   │
   ▼
DeepSeek 视觉模型分析图片 (Anthropic 兼容 API，思考模式)
   │
   ▼
企微长连接 aibot_send_msg —— 推送「答案」到会话
```

## 环境要求

- Windows 10 / 11
- Python 3.10+（建议 3.12，可用 conda）

## 安装

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

## 配置

复制模板并填入你的密钥：

```bash
copy config.example.json config.json
```

然后编辑 `config.json`：

| 字段 | 说明 |
|---|---|
| `model.api_key` | DeepSeek API Key（在 [DeepSeek 开放平台](https://platform.deepseek.com) 申请，`sk-` 开头） |
| `model.model_name` | 视觉模型名，默认 `deepseek-v4-flash-vision-exp` |
| `model.reasoning_effort` | 思考强度：`low` / `high` / `max`（`high` 快且准，`max` 更强但更慢） |
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
4. 在企微里搜索该机器人并**添加为好友**（单聊）。

## 运行

```bash
conda activate offer-screenshot   # 若用 conda
python main.py
```

或直接双击 [`run.bat`](run.bat)（内置 conda activate，仅适用于使用 conda 的用户）。

使用流程：

1. 看到 `✅ 会话已绑定`（或等待连接成功）。
2. **在企微里给机器人发一条消息**（任意内容），用于激活会话——企微规则要求用户先发消息，机器人才可主动推送。
3. 按 `Ctrl+Alt+S`，拖拽框选屏幕上的题目区域。
4. 截图 + AI 答案会依次出现在企微会话里。

## 文件结构

```
main.py              主入口：快捷键监听 + 截图编排 + 模型调用
capture.py           截图：静默全屏 + 无焦点框选（防失焦检测）
llm_client.py        DeepSeek 视觉模型调用（Anthropic 兼容 API）
wecom_bot.py         企微智能机器人长连接客户端（WebSocket）
config.example.json  配置模板（脱敏）
requirements.txt     依赖
run.bat              Windows 一键启动（conda）
tools/check_model.py 模型连通性检查脚本
```

## 常见问题

- **没有「会话已绑定」提示**：必须先在企微里给机器人**发一条消息**，机器人才可主动推送。
- **图片发送失败**：代码已压缩为 JPEG 且控制在 2MB 内；仍失败请缩小框选范围。
- **模型 400/401 错误**：确认 `model.api_key` 有效、`base_url` 为 `https://api.deepseek.com/anthropic`。
- **模型不输出答案 / 返回 JSON**：通常是截图太糊或题目过难导致思考超限，请截图更清晰、缩小范围，或调大 `max_tokens`。
- **高分屏框选偏移**：代码已做 DPI 感知；仍有问题可把 Windows 显示缩放设为 100%。
- **连接频繁断开**：程序内置 30 秒心跳 + 指数退避重连；持续失败请检查网络或 `bot_id/secret`。

## 技术要点

- **企微长连接协议**：`aibot_subscribe` 鉴权 → 30s `ping` 心跳 → `aibot_msg_callback` 收消息 → `aibot_send_msg` 主动发送；响应帧用 `headers.req_id` 关联。
- **图片上传**：`aibot_upload_media_init` → 分片 `chunk`（≤512KB）→ `finish` 拿 `media_id` → 发 `image` 消息。
- **思考模式**：`thinking: {"type": "enabled"}` + `output_config.effort`。关掉思考会导致答案算错，务必开启。
- **防失焦截图**：先 `ImageGrab.grab()` 静默全屏截图，再弹无焦点遮罩（`WS_EX_NOACTIVATE`）框选，全程不抢焦点。

## License

[MIT](LICENSE) © 2026 Yyy-sh
