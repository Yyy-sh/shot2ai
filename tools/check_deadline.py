"""检查 60 秒硬截止：模型卡住时必须按时发超时提示，绝不发迟到的答案。

用法：python tools/check_deadline.py
（用缩短的截止时间跑，只为快速验证逻辑；真实值 60 秒见 main.DEADLINE_S）
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image  # noqa: E402

import llm_client  # noqa: E402
import main  # noqa: E402


class FakeBot:
    def __init__(self):
        self.sent = []

    def get_user_chat(self):
        return ("target", 1, "user")

    def send_image(self, *a, **k):
        pass

    def send_markdown(self, target, chat_type, content):
        self.sent.append(content)


CFG = {
    "model": {"api_key": "x", "base_url": "x", "model_name": "x",
              "max_tokens": 8, "system_prompt": "s"},
    "user_prompt": "p",
}
IMG = Image.new("RGB", (50, 50), (255, 255, 255))


def run(analyze_impl, deadline):
    main.DEADLINE_S = deadline
    main.SEND_RESERVE_S = 0.3
    llm_client.analyze_image = analyze_impl
    bot = FakeBot()
    t = time.time()
    main.process_and_reply(bot, CFG, IMG)
    return time.time() - t, bot.sent


# 1) 模型卡死 → 必须在截止时间内发出超时提示，且不发任何答案
elapsed, sent = run(lambda *a, **k: time.sleep(30), 3)
assert elapsed < 3.6, f"超过了截止时间：{elapsed:.1f}s"
assert sent and "超过" in sent[-1], f"未发出超时提示：{sent}"
print(f"✅ 卡死用例：{elapsed:.1f}s 发出「{sent[-1]}」")

# 2) 模型正常 → 正常发答案
elapsed, sent = run(lambda *a, **k: "解题答案", 3)
assert sent and sent[-1] == "解题答案", f"答案未发出：{sent}"
print(f"✅ 正常用例：{elapsed:.1f}s 发出「{sent[-1]}」")

print("\n60 秒硬截止逻辑正常。")
