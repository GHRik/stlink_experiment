"""Create the desktop window and connect its Python bridge."""
from pathlib import Path
import ctypes
import sys

def run_desktop(webview, demo=False):
    if sys.platform == 'win32':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            'GHRik.STLINK.PowerMeasurements' + ('.Demo' if demo else ''))
    icon = Path(__file__).resolve().parents[1] / 'frontend/assets' / ('stlink-demo.ico' if demo else 'stlink.ico')
    api = None
    if not demo:
        from .api import DesktopApi
        from .config import load_settings
        api = DesktopApi(webview, load_settings())
    window = webview.create_window(
        "STLINK power measurements" + (" — Demo" if demo else ""),
        url=str(Path(__file__).resolve().parents[1] / "frontend" / "index.html"),
        js_api=api,
        width=1440,
        height=960,
        min_size=(900, 600),
        maximized=True,
        text_select=True,
    )
    if api is not None:
        api._bind_window(window)
        window.events.closing += api._on_closing
    webview.start(icon=str(icon))
