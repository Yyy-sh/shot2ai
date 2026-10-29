"""自检：三连点判定（不碰真鼠标，直接喂事件）。

判定规则：相邻两下间隔 ≤ TRIPLE_GAP_S、三下漂移 ≤ TRIPLE_RADIUS 像素，
命中时返回第一下的坐标（左键按下位置）。

用法：python tools/check_triple_click.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from capture import TripleClickDetector  # noqa: E402

bad: list = []


def feed(det, events):
    """events: [(间隔秒, x, y), ...]；返回最后一次 feed 的结果。"""
    t, out = 0.0, None
    for dt, x, y in events:
        t += dt
        out = det.feed(t, x, y)
    return out


def expect(label: str, got, want) -> None:
    if got != want:
        bad.append(f"{label}：期望 {want}，实得 {got}")


# 1. 快速三连点
expect("三下同点", feed(TripleClickDetector(), [(0, 100, 100), (0.12, 100, 100), (0.12, 100, 100)]),
       (100, 100))
# 2. 只有两下不算
expect("只有两下", feed(TripleClickDetector(), [(0, 100, 100), (0.12, 100, 100)]), None)
# 3. 间隔太久（每次 0.7 秒）不算
expect("间隔太久", feed(TripleClickDetector(), [(0, 100, 100), (0.7, 100, 100), (0.7, 100, 100)]), None)
# 4. 三下位置差太多（手离开原地）不算
expect("位置漂移过大", feed(TripleClickDetector(), [(0, 100, 100), (0.12, 140, 100), (0.12, 100, 100)]),
       None)
# 5. 轻微手抖仍算，取第一下的坐标
expect("手抖 ≤8px", feed(TripleClickDetector(), [(0, 100, 100), (0.1, 104, 97), (0.1, 97, 103)]),
       (100, 100))
# 6. 命中后重新计数，接着再连点三下还能命中
expect("命中后再次三连点", feed(TripleClickDetector(),
                                [(0, 10, 20), (0.1, 10, 20), (0.1, 10, 20),
                                 (0.1, 30, 40), (0.1, 30, 40), (0.1, 30, 40)]), (30, 40))
# 7. 两次在 A、第三下跳到 B：不算；之后 B 三连点照常命中
expect("两下 A 一下 B 后连点 B", feed(TripleClickDetector(),
                                      [(0, 10, 10), (0.1, 10, 10), (0.1, 200, 200),
                                       (0.1, 200, 200), (0.1, 200, 200), (0.1, 200, 200)]),
       (200, 200))

if bad:
    print("[FAIL] 三连点判定有问题：")
    for m in bad:
        print("   -", m)
    raise SystemExit(1)
print("[OK] 三连点判定正常：快速三下命中、两下/过慢/漂移过大不触发，命中后可重新计数。")
