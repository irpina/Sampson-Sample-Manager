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
        try:
            from AppKit import NSScreen  # provided by pyobjc-framework-Cocoa
            scale = NSScreen.mainScreen().backingScaleFactor()
            if scale and scale > 0:
                return float(scale)
        except Exception:
            pass
        return 1.0

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
