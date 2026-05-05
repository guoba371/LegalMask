import sys
import os
import webbrowser
import threading
import time
from pathlib import Path

# 确保 core 模块可以被找到（PyInstaller打包后路径不同）
if getattr(sys, 'frozen', False):
    base_dir = Path(sys._MEIPASS)
    sys.path.insert(0, str(base_dir))

from streamlit.web import cli as stcli

def main():
    app_path = Path(__file__).parent / "app.py"
    if getattr(sys, 'frozen', False):
        app_path = Path(sys._MEIPASS) / "app.py"

    sys.argv = [
        "streamlit", "run", str(app_path),
        "--server.port=8501",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.fileWatcherType=none",
        "--global.developmentMode=false",
    ]
    
    # macOS: 等待服务器启动后自动打开浏览器
    if sys.platform == "darwin":
        def open_browser():
            time.sleep(3)
            webbrowser.open("http://localhost:8501")
        threading.Thread(target=open_browser, daemon=True).start()
    
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
