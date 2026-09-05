"""截图模块：静默全屏截图 + 无焦点裁剪窗口（不触发网页失焦检测）。

核心思路：
  1. 按快捷键后先用 ImageGrab.grab() 全屏截图（不创建窗口、不抢焦点），
     题目已悄悄存入内存 —— 此时浏览器不会失焦，不触发防作弊警告。
  2. 然后才弹出裁剪窗口框选；窗口设 WS_EX_NOACTIVATE 不抢焦点，警告都不会弹。
  3. 框选完从已截图裁剪，不需要第二次截图。
"""
import ctypes
import time
import tkinter as tk
from typing import Optional

from PIL import Image, ImageGrab


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


def capture_region() -> Optional[Image.Image]:
    """静默全屏截图 + 无焦点裁剪窗口框选。

    流程：
      1. ImageGrab.grab() 全屏截图（不抢焦点，题目已存内存）
      2. 弹无焦点遮罩窗口框选（不抢焦点，不触发失焦警告）
      3. 从已截图裁剪，返回题目区域
    """
    _setup_dpi_awareness()
    time.sleep(0.05)  # 等快捷键释放，避免截到按键状态

    # —— 步骤1：静默全屏截图（此刻不创建任何窗口，浏览器不失焦）——
    full = ImageGrab.grab()
    sw, sh = full.size

    # —— 步骤2：弹无焦点遮罩窗口框选 ——
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

    def on_press(event):
        state["start"] = (event.x, event.y)
        if state["rect"] is not None:
            canvas.delete(state["rect"])
        state["rect"] = canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#00ff66", width=2,
        )

    def on_drag(event):
        if state["rect"] is not None:
            x0, y0 = state["start"]
            canvas.coords(state["rect"], x0, y0, event.x, event.y)

    def on_release(event):
        x0, y0 = state["start"]
        x1, y1 = event.x, event.y
        left, top = min(x0, x1), min(y0, y1)
        right, bottom = max(x0, x1), max(y0, y1)
        state["bbox"] = (left, top, right, bottom) if (right - left >= 5 and bottom - top >= 5) else None
        root.withdraw()
        root.quit()

    def on_escape(_event):
        state["bbox"] = None
        root.withdraw()
        root.quit()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    root.bind("<Escape>", on_escape)

    root.mainloop()

    bbox = state["bbox"]
    root.destroy()
    if bbox is None:
        return None

    # —— 步骤3：从已截的全屏图裁剪（不再次截图）——
    return full.crop(bbox)
