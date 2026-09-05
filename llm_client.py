"""调用 DeepSeek 视觉模型分析截图（Anthropic 兼容 Messages API 格式）。

DeepSeek /anthropic 端点兼容 Anthropic Messages API：
  POST {base_url}/v1/messages
  鉴权同时带 x-api-key 与 Authorization: Bearer（双保险）
  必须带 anthropic-version: 2023-06-01
  thinking: {"type": "enabled"} + output_config.effort=high 开启推理（否则答案会算错）
  effort 档位 low/high/max：high 最快且正确，max 更强但更慢（复杂题可能逼近 60s）
  图片压缩后再发（长边≤960，JPEG，可通过 config 的 model.max_side 调整），大幅降低模型处理延迟。
"""
import base64
import io

import requests
from PIL import Image


def image_to_base64(img: Image.Image, max_side: int = 960, quality: int = 80) -> str:
    """PIL 图片压缩成 JPEG 再转 base64（不带 data: 前缀）。

    长边缩到 max_side，JPEG quality 压缩，base64 体积大幅下降，
    模型处理更快。视觉模型 1280px 足够看清题目文字。
    """
    rgb = img.convert("RGB")
    w, h = rgb.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        rgb = rgb.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    buf = io.BytesIO()
    rgb.save(buf, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def analyze_image(
    img: Image.Image,
    api_key: str,
    base_url: str,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1024,
    timeout: int = 55,
    max_side: int = 960,
    reasoning_effort: str = "high",
) -> str:
    """把截图交给 DeepSeek 视觉模型分析，返回文本答案。

    timeout 默认 55 秒，确保整体不超 60 秒。
    reasoning_effort 控制思考强度 low/high/max，默认 high（快且准）。
    """
    url = base_url.rstrip("/") + "/v1/messages"
    # 双鉴权头：x-api-key（Anthropic 原生）+ Authorization: Bearer（网关兼容）
    headers = {
        "x-api-key": api_key,
        "Authorization": f"Bearer {api_key}",
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model_name,
        "max_tokens": max_tokens,
        "thinking": {"type": "enabled"},
        "output_config": {"effort": reasoning_effort},
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_to_base64(img, max_side=max_side),
                        },
                    },
                ],
            }
        ],
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        print(f"[模型] HTTP {resp.status_code} 错误响应: {resp.text[:1000]}")
        resp.raise_for_status()

    data = resp.json()
    # Anthropic 兼容格式：content 是 block 列表，取第一个 text block
    # 开启 thinking 时 content 里会有 thinking 块 + text 块，跳过 thinking 取 text
    for block in data.get("content", []):
        if block.get("type") == "text":
            return block.get("text", "")

    # 兜底：某些实现可能直接返回 choices（OpenAI 兼容）
    if "choices" in data:
        return data["choices"][0]["message"]["content"]

    # 没有 text 块：通常是 thinking 吃满了 max_tokens（图太糊/题目太难）
    if data.get("stop_reason") == "max_tokens":
        return "（模型思考超限，未生成答案。请截图更清晰/缩小范围后重试。）"
    return str(data)
