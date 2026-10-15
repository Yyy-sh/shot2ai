"""检查快捷键：单键（F8）与组合键都要能正确触发。

坑点：pynput 监听器送达的是 Key.f8，但 GlobalHotKeys 会先做 canonical()
把它变成 KeyCode(vk=119)，而 HotKey.parse('<f8>') 也给 KeyCode(vk=119) —— 靠这
一步才对得上。**所以必须走 GlobalHotKeys + canonical 的真实路径来测**；直接拿
HotKey 状态机喂 Key.f8 会误判成"单键不支持"。

用法：python tools/check_hotkey.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pynput import keyboard  # noqa: E402

import main  # noqa: E402

K = keyboard.Key
C = keyboard.KeyCode.from_char


def build(combo: str):
    """按 main.py 的方式建监听器，返回 (listener, 触发次数列表)。"""
    fired = []
    listener = keyboard.GlobalHotKeys({main._pynput_hotkey(combo): lambda: fired.append(1)})
    return listener, fired


def fires(combo: str, presses: list) -> int:
    """全部按下（模拟真实非注入事件）再全部松开，返回触发次数。"""
    listener, fired = build(combo)
    for k in presses:
        listener.on_press(k, False)
    for k in reversed(presses):
        listener.on_release(k, False)
    return len(fired)


bad: list = []


def expect(label: str, got, want) -> None:
    if got != want:
        bad.append(f"{label}：期望 {want}，实得 {got}")


expect("单键 f8", fires("f8", [K.f8]), 1)
expect("单键 f9", fires("f9", [K.f9]), 1)
expect("单键 f12", fires("f12", [K.f12]), 1)
expect("组合 ctrl+alt+s", fires("ctrl+alt+s", [K.ctrl, K.alt, C("s")]), 1)
expect("组合 alt+s", fires("alt+s", [K.alt, C("s")]), 1)
expect("f8 配置按 f9", fires("f8", [K.f9]), 0)
expect("f8 配置按普通字母", fires("f8", [C("a")]), 0)
expect("ctrl+alt+s 只按 s", fires("ctrl+alt+s", [C("s")]), 0)

# 长按不重复触发
listener, fired = build("f8")
listener.on_press(K.f8, False)
listener.on_press(K.f8, False)
listener.on_press(K.f8, False)
expect("长按 f8 重复触发", len(fired), 1)

# 松开后可再次触发
listener.on_release(K.f8, False)
listener.on_press(K.f8, False)
expect("松开后再按", len(fired), 2)

# 注入（合成/脚本）按键必须被忽略，否则别的程序敲 F8 会误触发截图
listener, fired = build("f8")
listener.on_press(K.f8, True)
expect("注入事件被过滤", len(fired), 0)

if bad:
    print("❌ 快捷键有问题：")
    for m in bad:
        print("   -", m)
    raise SystemExit(1)
print("✅ 快捷键正常：单键（f8/f9/f12）与组合键（ctrl+alt+s / alt+s）均可触发，"
      "长按不重复，注入事件被过滤。")
