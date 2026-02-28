"""PyInstaller runtime hook: silence Tcl/Tk 9.0 console deprecation warning.

This MUST run before tkinter is imported to prevent the console window crash
in signed PyInstaller bundles on macOS.
"""
import os
os.environ["TK_SILENCE_DEPRECATION"] = "1"
