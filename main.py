"""主入口：企微长连接机器人 + 快捷键截图 → 视觉分析 → 回复到企微会话。

架构：
  - 后台线程：企微 WebSocket 长连接（收消息、心跳、绑定会话）
  - 后台线程：pynput 全局快捷键监听
  - 主线程：轮询快捷键信号 → 在主线程执行 tkinter 框选截图 → 起后台线程调模型 + 推送企微
（tkinter 必须在主线程创建，所以截图在主线程做。）
"""
import io
import json
import os
import threading
import time

from pynput import keyboard

import capture
import llm_client
from wecom_bot import WeComBot

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _pynput_hotkey(hotkey: str) -> str:
    """把 'ctrl+alt+s' 转成 pynput 的 '<ctrl>+<alt>+s' 格式。"""
    mapping = {
        "ctrl": "<ctrl>", "control": "<ctrl>",
        "alt": "<alt>", "option": "<alt>",
        "shift": "<shift>",
        "cmd": "<cmd>", "win": "<cmd>", "super": "<cmd>",
    }

    def norm(part: str) -> str:
        part = part.strip().lower()
        if part.startswith("f") and part[1:].isdigit():
            return f"<{part}>"
        return mapping.get(part, part)

    return "+".join(norm(p) for p in hotkey.split("+"))


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    m = cfg["model"]
    if not m.get("api_key"):
        raise SystemExit("请先在 config.json 填写 model.api_key")
    wb = cfg["wecom_bot"]
    if not wb.get("bot_id") or not wb.get("secret"):
        raise SystemExit("请先在 config.json 填写 wecom_bot.bot_id / secret")
    m.setdefault("max_tokens", 1536)
    m.setdefault("max_side", 960)
    m.setdefault("system_prompt", "你是专业的笔试/面试解题助手。请仔细阅读图片中的题目，给出准确、简洁的答案，并附上简要的解题思路或解析。")
    cfg.setdefault("hotkey", "ctrl+alt+s")
    cfg.setdefault("capture_mode", "region")
    cfg.setdefault("user_prompt", "请分析这张截图中的题目并作答。")
    return cfg


# 从进入处理到答案发出，硬上限 60 秒；留 2 秒余量给企微发送
DEADLINE_S = 60
SEND_RESERVE_S = 2


def process_and_reply(bot: WeComBot, cfg: dict, img) -> None:
    """截图 → 并行（发图到企微 + 调模型分析）→ 回复答案。"""
    start = time.time()

    def remaining() -> float:
        """距离硬截止还剩多少秒（含发送余量扣减）。"""
        return DEADLINE_S - SEND_RESERVE_S - (time.time() - start)

    m = cfg["model"]
    chat = bot.get_user_chat()
    if not chat:
        print("⚠️ 还没有用户给机器人发过消息，无法推送。请先在企微给机器人发条消息激活会话。")
        return
    target, chat_type, userid = chat

    # 预压缩截图（供发企微用）
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=85)
    if buf.tell() > 2 * 1024 * 1024:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=60)
    img_bytes = buf.getvalue()

    answer_holder = {"answer": None, "error": None}

    # 线程B：调模型分析（与发图并行，不等发图）
    def analyze():
        try:
            print("[模型] 开始分析截图 ...")
            answer_holder["answer"] = llm_client.analyze_image(
                img,
                api_key=m["api_key"],
                base_url=m["base_url"],
                model_name=m["model_name"],
                system_prompt=m["system_prompt"],
                user_prompt=cfg["user_prompt"],
                max_tokens=m["max_tokens"],
                max_side=m.get("max_side", 960),
                reasoning_effort=m.get("reasoning_effort", "high"),
                timeout=max(5, remaining()),   # 请求超时与总截止时间对齐
            )
        except Exception as e:
            answer_holder["error"] = e

    t_analyze = threading.Thread(target=analyze, daemon=True)
    t_analyze.start()

    # 线程A：发图到企微（与模型分析并行；最多等 10 秒，避免上传卡死拖垮 60 秒保证）
    def send_shot():
        try:
            print("[企微] 发送截图 ...")
            bot.send_image(target, chat_type, img_bytes, "screenshot.jpg")
            bot.send_markdown(target, chat_type, "🤖 已收到截图，正在分析 ...")
        except Exception as e:
            print(f"[企微] 发图出错（不影响分析）: {e}")

    t_send = threading.Thread(target=send_shot, daemon=True)
    t_send.start()
    t_send.join(timeout=min(10, max(0.1, remaining())))

    # 等模型分析完，发答案（最多等到硬截止，确保整体不超 60 秒）
    print("[模型] 等待分析结果 ...")
    t_analyze.join(timeout=max(0.1, remaining()))
    if t_analyze.is_alive():
        answer_holder["error"] = f"分析超过 {DEADLINE_S} 秒未完成，已放弃本次答案"
    if answer_holder["error"]:
        err = answer_holder["error"]
        print(f"❌ 模型出错: {err}")
        try:
            bot.send_markdown(target, chat_type, f"❌ 分析出错：{err}")
        except Exception:
            pass
        return

    print("[企微] 发送答案 ...")
    bot.send_markdown(target, chat_type, answer_holder["answer"])
    print("✅ 完成。\n")


def main() -> None:
    cfg = load_config()
    wb = cfg["wecom_bot"]

    # 启动企微长连接
    bot = WeComBot(wb["bot_id"], wb["secret"], wb.get("ws_url", "wss://openws.work.weixin.qq.com"))
    bot.connect()
    print("正在连接企微长连接 ...")

    # 等待用户首次发消息绑定会话
    def wait_chat():
        chat = bot.wait_for_chat()
        if chat:
            print(f"✅ 会话已绑定（target={chat[0]}）。按 {cfg['hotkey']} 截图提问；Ctrl+C 退出。")
    threading.Thread(target=wait_chat, daemon=True).start()

    # 快捷键信号队列
    signals = []

    def on_hotkey():
        signals.append(1)

    listener = keyboard.GlobalHotKeys({_pynput_hotkey(cfg["hotkey"]): on_hotkey})
    listener.start()

    print(f"⏳ 等待企微认证与首次会话 ...（先在企微里给机器人发条消息）")

    try:
        while True:
            if signals:
                signals.pop()
                # 截图必须在主线程做（tkinter）
                mode = cfg.get("capture_mode", "region")
                img = capture.capture_region() if mode == "region" else capture.capture_fullscreen()
                if img is None:
                    print("已取消截图。\n")
                    continue
                print(f"截图尺寸: {img.size}")
                # 模型调用 + 推送放到后台线程，不阻塞主线程
                threading.Thread(target=process_and_reply, args=(bot, cfg, img), daemon=True).start()
            time.sleep(0.15)
    except KeyboardInterrupt:
        print("\n已退出。")
    finally:
        listener.stop()
        bot.stop()


if __name__ == "__main__":
    main()
