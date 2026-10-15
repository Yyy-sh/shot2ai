"""校准工具：框选一次题目区域，把坐标写进 config.json，之后截图零屏幕变化。

用法：python tools/pick_region.py
然后把 config.json 的 capture_mode 设为 "fixed"（本脚本会自动设）。

注意：题目区域的位置要固定（比如刷题网页每次都在同一个位置）。
换分辨率、换窗口位置、缩放网页后需重新校准。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import capture  # noqa: E402

CFG_PATH = os.path.join(ROOT, "config.json")

with open(CFG_PATH, "r", encoding="utf-8") as f:
    cfg = json.load(f)

print("请框选题目区域（松开确认，ESC 取消）...")
bbox = capture.pick_bbox()
if not bbox:
    print("已取消，配置未改动。")
    raise SystemExit(0)

cfg["capture_bbox"] = list(bbox)
cfg["capture_mode"] = "fixed"
with open(CFG_PATH, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
    f.write("\n")

print(f"✅ capture_bbox = {list(bbox)}，capture_mode = fixed")
print("之后按快捷键截图不再弹任何窗口，屏幕零变化。")
