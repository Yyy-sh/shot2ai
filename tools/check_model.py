"""模型连通性检查：验证 config.json 里的视觉模型 key / 端点 / 视觉能力是否正常。

用法：
    python tools/check_model.py

会用一道内置题目渲染成图片，走一次完整的 analyze_image 流程，
打印状态码、耗时与答案，帮助排查 key 无效 / 模型不支持图片 / 网络不通等问题。
"""
import json
import os
import sys
import time

# 让脚本无论从哪个目录运行都能找到项目根目录的 config 与模块
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw  # noqa: E402

import llm_client  # noqa: E402


def main() -> None:
    cfg_path = os.path.join(ROOT, "config.json")
    if not os.path.exists(cfg_path):
        print(f"❌ 找不到 {cfg_path}，请先 `copy config.example.json config.json` 并填入密钥。")
        sys.exit(1)

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)["model"]

    print(f"模型: {cfg['model_name']}")
    print(f"端点: {cfg['base_url']}")
    print(f"思考强度: {cfg.get('reasoning_effort', 'high')}")
    print("正在生成测试图片并调用模型 ...\n")

    # 渲染一道简单题目（纯 ASCII，不依赖中文字体）
    img = Image.new("RGB", (400, 120), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 40), "12 x 15 = ?", fill=(0, 0, 0))

    t = time.time()
    try:
        ans = llm_client.analyze_image(
            img,
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
            model_name=cfg["model_name"],
            system_prompt=cfg["system_prompt"],
            user_prompt="读出算式并计算，只给答案。",
            max_tokens=cfg.get("max_tokens", 2048),
            max_side=cfg.get("max_side", 960),
            reasoning_effort=cfg.get("reasoning_effort", "high"),
        )
    except Exception as e:
        print(f"❌ 调用失败（{time.time() - t:.1f}s）：{e}")
        sys.exit(1)

    print(f"✅ 成功（{time.time() - t:.1f}s）")
    print(f"答案：{ans[:200]}")
    if "180" in ans:
        print("（识别与计算正确）")


if __name__ == "__main__":
    main()
