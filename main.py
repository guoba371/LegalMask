"""LegalMask desktop launcher for Windows and macOS."""

from __future__ import annotations

import argparse
import asyncio
import html
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


APP_NAME = "LegalMask"
APP_TITLE = "LegalMask — 律师文件脱敏助手"


def _resource_path(relative_path: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / relative_path


def _user_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        path = base / APP_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        path = Path.home() / ".local" / "share" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _log_path() -> Path:
    log_dir = _user_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "legalmask.log"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _configure_streamlit(port: int) -> None:
    from streamlit import config

    options = {
        "server.port": port,
        "server.address": "127.0.0.1",
        "server.headless": True,
        "server.fileWatcherType": "none",
        "browser.gatherUsageStats": False,
        "global.developmentMode": False,
    }
    for key, value in options.items():
        config.set_option(key, value)


class DesktopServer:
    def __init__(self) -> None:
        self.port = _find_free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.health_url = f"{self.url}/_stcore/health"
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server = None
        self._thread: threading.Thread | None = None
        self._error: BaseException | None = None

    def start(self) -> None:
        _configure_streamlit(self.port)
        from streamlit.web.server import Server

        app_path = _resource_path("app.py")
        if not app_path.exists():
            raise FileNotFoundError(f"Application entry point not found: {app_path}")

        sys.path.insert(0, str(app_path.parent))
        self._server = Server(str(app_path), False)
        self._thread = threading.Thread(
            target=self._run_server,
            name="LegalMaskStreamlit",
            daemon=True,
        )
        self._thread.start()

    def _run_server(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._server.start())
            self._loop.run_until_complete(self._server.stopped)
        except BaseException as exc:
            self._error = exc
            logging.exception("Local Streamlit server failed")
        finally:
            self._loop.close()

    def wait_until_ready(self, timeout: float = 60.0) -> None:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._error is not None:
                raise RuntimeError(f"本地服务启动失败：{self._error}") from self._error
            if self._thread is not None and not self._thread.is_alive():
                raise RuntimeError("本地服务已意外退出。")
            try:
                with opener.open(self.health_url, timeout=1) as response:
                    if response.status == 200 and response.read().decode().strip() == "ok":
                        return
            except Exception:
                time.sleep(0.2)
        raise TimeoutError("本地服务启动超时，请查看日志。")

    def stop(self) -> None:
        if self._server is not None:
            try:
                self._server.stop()
            except Exception:
                logging.exception("Failed to stop local Streamlit server")
        if self._thread is not None:
            self._thread.join(timeout=8)


def _splash_html() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0; min-height: 100vh; display: grid; place-items: center;
      color: #102a36; background:
        radial-gradient(circle at 20% 10%, rgba(184,59,47,.13), transparent 38%),
        #f3eee2;
      font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
    }
    .splash { width: min(430px, calc(100vw - 56px)); text-align: center; }
    .mark {
      width: 58px; height: 58px; margin: 0 auto 26px; display: grid;
      place-items: center; border-radius: 15px; background: #102a36;
      color: #fff; font: 700 28px Georgia, serif;
    }
    h1 { margin: 0; font: 700 28px "Songti SC", SimSun, serif; letter-spacing: 1px; }
    p { margin: 12px 0 0; color: #5f7278; font-size: 13px; line-height: 1.8; }
    .track {
      height: 3px; margin-top: 30px; overflow: hidden; background: #d9d2c3;
    }
    .track:after {
      content: ""; display: block; width: 34%; height: 100%;
      background: #b83b2f; animation: load 1.1s ease-in-out infinite;
    }
    @keyframes load {
      from { transform: translateX(-110%); }
      to { transform: translateX(310%); }
    }
  </style>
</head>
<body>
  <div class="splash">
    <div class="mark">L</div>
    <h1>LegalMask</h1>
    <p>正在启动本地脱敏引擎<br>首次打开可能需要几秒钟，请稍候</p>
    <div class="track"></div>
  </div>
</body>
</html>
"""


def _error_html(message: str, log_path: Path) -> str:
    return f"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    body {{
      margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 30px;
      color: #102a36; background: #f3eee2;
      font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
    }}
    .error {{ width: min(620px, 100%); padding: 34px; background: #fffdf8; border: 1px solid #d9d2c3; }}
    h1 {{ margin: 0 0 16px; font: 700 25px "Songti SC", SimSun, serif; }}
    p, code {{ color: #5f7278; font-size: 13px; line-height: 1.8; }}
    code {{ display: block; padding: 12px; overflow-wrap: anywhere; background: #f3eee2; }}
  </style>
</head>
<body>
  <div class="error">
    <h1>LegalMask 启动失败</h1>
    <p>{html.escape(message)}</p>
    <p>请关闭窗口后重新打开。如问题持续，请将下面的日志文件发给技术支持：</p>
    <code>{html.escape(str(log_path))}</code>
  </div>
</body>
</html>
"""


def _load_desktop_application(
    window,
    server: DesktopServer,
    log_path: Path,
    navigation_timeout: float = 60.0,
) -> None:
    try:
        logging.info("Waiting for Streamlit server to be ready...")
        server.wait_until_ready()
        logging.info(f"Server ready at {server.url}, loading URL in window...")
        
        # Test WebView JS engine before loading URL
        try:
            test_result = window.evaluate_js("1+1")
            logging.info(f"WebView JS test: 1+1={test_result}")
        except Exception as e:
            logging.error(f"WebView JS engine test failed: {e}")
            raise RuntimeError("WebView JavaScript 引擎初始化失败") from e
        
        # Load URL
        window.load_url(server.url)
        logging.info("URL loaded, waiting for page ready...")
        
        # Poll document.readyState with detailed logging
        deadline = time.monotonic() + navigation_timeout
        page_loaded = False
        last_state = None
        attempts = 0
        
        while time.monotonic() < deadline:
            try:
                result = window.evaluate_js("document.readyState")
                attempts += 1
                
                if result != last_state:
                    logging.info(f"readyState changed: {last_state} -> {result} (attempt {attempts})")
                    last_state = result
                
                if result in ("interactive", "complete"):
                    logging.info(f"Page loaded successfully (readyState={result}, {attempts} attempts)")
                    page_loaded = True
                    break
            except Exception as e:
                if attempts % 10 == 1:  # Log every 10th error to avoid spam
                    logging.warning(f"Error checking readyState (attempt {attempts}): {e}")
            
            time.sleep(0.5)
        
        if not page_loaded:
            logging.error(f"Page load timeout after {attempts} attempts, last_state={last_state}")
            raise TimeoutError(
                f"LegalMask 页面加载超时（{server.url}，{navigation_timeout}秒）。请查看日志后重试。"
            )
    except Exception as exc:
        logging.exception(f"Failed to load LegalMask UI: {exc}")
        try:
            window.load_html(_error_html(str(exc), log_path))
        except Exception as e2:
            logging.exception(f"Failed to display error page: {e2}")


def _show_browser_fallback(server: DesktopServer) -> None:
    try:
        server.wait_until_ready(timeout=30)
    except Exception as exc:
        logging.exception("Fallback browser startup failed")
        raise RuntimeError(str(exc)) from exc

    webbrowser.open(server.url)

    import tkinter as tk

    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("460x210")
    root.resizable(False, False)
    root.configure(bg="#f3eee2")
    tk.Label(
        root,
        text="LegalMask 已在浏览器中打开",
        bg="#f3eee2",
        fg="#102a36",
        font=("Microsoft YaHei" if sys.platform == "win32" else "PingFang SC", 16, "bold"),
    ).pack(pady=(35, 8))
    tk.Label(
        root,
        text="请使用浏览器窗口操作。关闭此窗口将退出 LegalMask。",
        bg="#f3eee2",
        fg="#5f7278",
        font=("Microsoft YaHei" if sys.platform == "win32" else "PingFang SC", 10),
    ).pack()
    tk.Button(
        root,
        text="重新打开浏览器",
        command=lambda: webbrowser.open(server.url),
        padx=18,
        pady=5,
    ).pack(pady=(22, 0))
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


def _run_desktop() -> int:
    log_path = _log_path()
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
    )

    server = DesktopServer()
    server.start()

    try:
        import webview

        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        window = webview.create_window(
            APP_TITLE,
            html=_splash_html(),
            width=1240,
            height=860,
            min_size=(900, 640),
            background_color="#f3eee2",
            text_select=True,
            confirm_close=False,
        )

        icon_path = _resource_path(
            "assets/icon.ico" if sys.platform == "win32" else "assets/icon.png"
        )
        webview.start(
            _load_desktop_application,
            args=(window, server, log_path),
            debug=os.environ.get("LEGALMASK_DEBUG") == "1",
            private_mode=False,
            storage_path=str(_user_data_dir() / "webview"),
            icon=str(icon_path) if icon_path.exists() else None,
        )
    except Exception:
        logging.exception("Native desktop window unavailable; using browser fallback")
        _show_browser_fallback(server)
    finally:
        server.stop()
    return 0


def _run_smoke_test() -> int:
    server = DesktopServer()
    try:
        from core.processor import _get_ocr_engine

        _get_ocr_engine()
        server.start()
        server.wait_until_ready(timeout=90)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(server.url, timeout=5) as response:
            if response.status != 200:
                raise RuntimeError(f"Unexpected HTTP status: {response.status}")
        print(f"LegalMask desktop and OCR smoke test passed: {server.url}")
        return 0
    finally:
        server.stop()


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--smoke-test", action="store_true")
    args, _ = parser.parse_known_args()
    if args.smoke_test:
        return _run_smoke_test()
    return _run_desktop()


if __name__ == "__main__":
    raise SystemExit(main())
