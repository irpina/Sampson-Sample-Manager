import sys
import ctypes

import state


def _enable_dpi_awareness():
    """
    Declare per-system DPI awareness so Windows renders the window at native
    resolution instead of bitmap-scaling it (which causes blurriness on
    HiDPI / 4K displays).  Must be called before tk.Tk() is created.
    """
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)   # PROCESS_SYSTEM_DPI_AWARE
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()    # Win Vista/7 fallback
        except (AttributeError, OSError):
            pass


def _compute_dpi_scale() -> float:
    """
    Return the DPI scale factor relative to the 96-DPI baseline.

    96 DPI  → 1.0   (100 % Windows display scale)
    120 DPI → 1.25  (125 %)
    144 DPI → 1.5   (150 %)
    192 DPI → 2.0   (200 %)

    macOS: Returns backingScaleFactor (1.0 on non-Retina, 2.0 on Retina).
    """
    if sys.platform == "darwin":
        return 1.0  # tkinter uses logical points; CTK handles Retina internally

    if sys.platform != "win32":
        return 1.0

    try:
        return ctypes.windll.shcore.GetDpiForSystem() / 96.0
    except (AttributeError, OSError):
        pass
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)   # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, hdc)
        return dpi / 96.0
    except (AttributeError, OSError):
        return 1.0


def _px(n: int) -> int:
    """Scale a pixel value by the current DPI factor (minimum 1)."""
    return max(1, int(n * state._dpi_scale))


# Minimum window dimensions (in pixels at 96 DPI baseline)
MIN_WINDOW_WIDTH = 900
MIN_WINDOW_HEIGHT = 600
MIN_ASPECT_RATIO = 1.38  # width/height - prevents extreme aspect ratios


def _usable_screen_size(root, desired_w: int, desired_h: int) -> tuple[int, int]:
    """
    Return (width, height) clamped to the usable screen area.

    On macOS, uses AppKit visibleFrame to exclude menu bar and dock.
    On other platforms, uses tkinter screen dimensions with no adjustment.
    """
    if sys.platform == "darwin":
        try:
            from AppKit import NSScreen
            frame = NSScreen.mainScreen().visibleFrame()
            max_w = int(frame.size.width) - 40   # small side margin
            max_h = int(frame.size.height) - 20  # small bottom margin
            return min(desired_w, max_w), min(desired_h, max_h)
        except Exception:
            pass
        # Fallback: tkinter screen size minus rough menu bar/dock estimate
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        return min(desired_w, sw - 40), min(desired_h, sh - 95)

    return desired_w, desired_h
