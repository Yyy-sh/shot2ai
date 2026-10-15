"""截图模块：三种模式，按 config 的 capture_mode 选择。

  region     —— 框选。先静默全屏截图，再弹无焦点遮罩（WS_EX_NOACTIVATE）框选，
                从已截图裁剪。屏幕会短暂出现半透明遮罩。
  fixed      —— 固定区域。不创建任何窗口，屏幕**零变化**（推荐，需先校准）。
  fullscreen —— 全屏。不创建任何窗口，屏幕**零变化**。

fixed / fullscreen 全程不弹窗、不抢焦点，屏幕看不出任何变化。
"""
import ctypes
import ctypes.wintypes
import time
import tkinter as tk
from typing import Optional

from PIL import Image, ImageGrab

# 遮罩窗口最长存活时间：忘按/误触快捷键时自动关闭，避免窗口赖在屏幕上不走
TIMEOUT_MS = 20_000
# 盲拖等待用户划出选区的最长时间
WAIT_DRAG_S = 20.0


def _setup_dpi_awareness() -> None:
    """让进程 DPI 感知，避免高分屏框选坐标与物理像素错位。"""
    try:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor aware
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _make_no_activate(root: tk.Tk) -> None:
    """让窗口不抢焦点（WS_EX_NOACTIVATE），避免触发浏览器失焦检测。

    即使遮罩窗口弹出，浏览器仍保持焦点，不触发"5秒返回"警告。
    """
    root.update_idletasks()  # 确保 hwnd 已创建
    # tkinter 顶层窗口的真正 Win32 句柄在 winfo_id() 的 parent
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    if not hwnd:
        hwnd = root.winfo_id()
    GWL_EXSTYLE = -20
    WS_EX_NOACTIVATE = 0x08000000   # 不激活、不抢焦点
    WS_EX_TOOLWINDOW = 0x00000080   # 不在任务栏显示
    WS_EX_TOPMOST = 0x00000008      # 置顶
    WS_EX_LAYERED = 0x00080000      # 支持半透明
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ctypes.windll.user32.SetWindowLongW(
        hwnd, GWL_EXSTYLE,
        style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_LAYERED,
    )


def capture_fullscreen() -> Image.Image:
    """静默截取整个屏幕（不创建窗口、不抢焦点）。"""
    _setup_dpi_awareness()
    time.sleep(0.05)  # 等快捷键释放，避免截到按键状态
    return ImageGrab.grab()


def wait_drag() -> Optional[tuple]:
    """不创建任何窗口，轮询全局鼠标等用户拖出一个矩形，返回 bbox。

    屏幕全程零变化 —— 代价是拖的时候看不见自己选了哪一块。
    左键拖拽，右键取消，超过 WAIT_DRAG_S 秒自动放弃。
    """
    u = ctypes.windll.user32
    VK_LBUTTON, VK_RBUTTON = 0x01, 0x02

    def down(vk: int) -> bool:
        return bool(u.GetAsyncKeyState(vk) & 0x8000)

    def cursor() -> tuple:
        pt = ctypes.wintypes.POINT()
        u.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    deadline = time.time() + WAIT_DRAG_S
    while not down(VK_LBUTTON):          # 等按下左键
        if down(VK_RBUTTON) or time.time() > deadline:
            return None
        time.sleep(0.01)

    x0, y0 = cursor()
    while down(VK_LBUTTON):              # 等松开左键
        if down(VK_RBUTTON) or time.time() > deadline:
            return None
        time.sleep(0.01)
    x1, y1 = cursor()

    left, top = min(x0, x1), min(y0, y1)
    right, bottom = max(x0, x1), max(y0, y1)
    if right - left < 5 or bottom - top < 5:
        return None
    return (left, top, right, bottom)


def pick_bbox(sw: Optional[int] = None, sh: Optional[int] = None) -> Optional[tuple]:
    """弹无焦点遮罩窗口让用户框选，返回 (left, top, right, bottom)。

    ESC 取消或区域过小则返回 None。窗口设 WS_EX_NOACTIVATE 不抢焦点，
    浏览器不会失焦。
    """
    _setup_dpi_awareness()
    if sw is None or sh is None:
        sw, sh = ImageGrab.grab().size

    root = tk.Tk()
    root.geometry(f"{sw}x{sh}+0+0")
    root.overrideredirect(True)        # 无边框
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.30)   # 半透明遮罩
    root.configure(bg="black")
    _make_no_activate(root)           # 关键：不抢焦点

    canvas = tk.Canvas(root, bg="black", highlightthickness=0, cursor="cross")
    canvas.pack(fill="both", expand=True)

    state = {"start": None, "rect": None, "bbox": None}

    canvas.create_text(
        20, 20, anchor="nw",
        text="拖拽框选题号区域，松开确认；ESC 取消",
        fill="#00ff66", font=("Microsoft YaHei", 14),
    )

    def close():
        root.withdraw()
        root.quit()

    # 看门狗：忘按/误触快捷键时自动关闭。盲拖模式窗口看不见却会吃掉所有点击，
    # 不自动关就只能重启进程。
    timer = {"id": None}

    def arm():
        if timer["id"] is not None:
            root.after_cancel(timer["id"])
        timer["id"] = root.after(TIMEOUT_MS, on_cancel)

    def on_press(event):
        arm()
        state["start"] = (event.x, event.y)
        if state["rect"] is not None:
            canvas.delete(state["rect"])
        state["rect"] = canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#00ff66", width=2,
        )

    def on_drag(event):
        arm()
        if state["rect"] is not None:
            x0, y0 = state["start"]
            canvas.coords(state["rect"], x0, y0, event.x, event.y)

    def on_release(event):
        if state["start"] is None:
            return
        x0, y0 = state["start"]
        x1, y1 = event.x, event.y
        left, top = min(x0, x1), min(y0, y1)
        right, bottom = max(x0, x1), max(y0, y1)
        state["bbox"] = (left, top, right, bottom) if (right - left >= 5 and bottom - top >= 5) else None
        close()

    def on_cancel(_event=None):
        state["bbox"] = None
        close()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    canvas.bind("<ButtonPress-3>", on_cancel)   # 右键取消（盲拖模式下窗口无键盘焦点）
    root.bind("<Escape>", on_cancel)
    arm()

    root.mainloop()

    bbox = state["bbox"]
    root.destroy()
    return bbox


def capture_region(blind: bool = False) -> Optional[Image.Image]:
    """静默全屏截图 + 框选。

    blind=False（默认）：弹无焦点遮罩，半透明 + 绿色选区框，屏幕短暂变灰。
    blind=True：不创建任何窗口，轮询鼠标取选区，屏幕全程零变化。
    """
    _setup_dpi_awareness()
    time.sleep(0.05)  # 等快捷键释放，避免截到按键状态
    full = ImageGrab.grab()

    bbox = wait_drag() if blind else pick_bbox(*full.size)
    if bbox is None:
        return None
    return full.crop(bbox)


def capture_fixed(bbox) -> Image.Image:
    """静默截取屏幕固定区域 —— 不创建任何窗口，屏幕全程零变化。

    bbox=(left, top, right, bottom)，物理像素（进程已 DPI 感知）。
    坐标用 tools/pick_region.py 校准一次即可。
    """
    _setup_dpi_awareness()
    time.sleep(0.05)  # 等快捷键释放，避免截到按键状态
    return ImageGrab.grab(bbox=tuple(bbox))


def grab(cfg: dict) -> Optional[Image.Image]:
    """按 config 的 capture_mode 截图。

    region     框选（有半透明遮罩）
    blind      盲拖：每次框选，但屏幕全程零变化
    fixed      固定区域，需 capture_bbox（无窗口，屏幕零变化）
    fullscreen 全屏（无窗口，屏幕零变化）
    """
    mode = cfg.get("capture_mode", "region")
    if mode == "region":
        return capture_region()
    if mode == "blind":
        print(f"🫥 盲拖：现在拖出题目区域（屏幕上不会有任何提示），右键取消。"
              f"{WAIT_DRAG_S:.0f} 秒内没动作就放弃。")
        return capture_region(blind=True)
    if mode == "fixed":
        bbox = cfg.get("capture_bbox")
        if bbox:
            return capture_fixed(bbox)
        print("⚠️ capture_mode=fixed 但没配 capture_bbox，已改用全屏截图。"
              "先跑 python tools/pick_region.py 校准。")
    return capture_fullscreen()
