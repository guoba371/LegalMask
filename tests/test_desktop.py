import socket
import unittest
from pathlib import Path

from main import DesktopServer, _find_free_port, _load_desktop_application


class _NeverLoadedEvent:
    def wait(self, timeout):
        return False


class _LoadedEvent:
    def wait(self, timeout):
        return True


class _FakeWindow:
    def __init__(self, loaded=True):
        self.loaded_url = None
        self.loaded_html = None
        self._page_loaded = loaded
        self._js_call_count = 0
        loaded_event = _LoadedEvent() if loaded else _NeverLoadedEvent()
        self.events = type("Events", (), {"loaded": loaded_event})()

    def load_url(self, url):
        self.loaded_url = url

    def load_html(self, content):
        self.loaded_html = content
    
    def evaluate_js(self, script):
        self._js_call_count += 1
        # First call is the test (1+1), always succeed
        if self._js_call_count == 1:
            return 2
        # Subsequent calls check document.readyState
        if self._page_loaded:
            return "complete"
        raise Exception("Page not loaded")


class _FakeServer:
    url = "http://127.0.0.1:54321"

    def wait_until_ready(self, timeout=60):
        self.ready_timeout = timeout


class DesktopLauncherTests(unittest.TestCase):
    def test_free_port_is_available_for_binding(self):
        port = _find_free_port()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", port))

    def test_desktop_server_starts_and_stops(self):
        server = DesktopServer()
        try:
            server.start()
            server.wait_until_ready(timeout=30)
            self.assertIn("127.0.0.1", server.url)
        finally:
            server.stop()

    def test_failed_page_navigation_shows_error_instead_of_blank_window(self):
        window = _FakeWindow(loaded=False)
        server = _FakeServer()

        with self.assertLogs(level="ERROR"):
            _load_desktop_application(
                window,
                server,
                Path("legalmask.log"),
                navigation_timeout=0.1,
            )

        self.assertEqual(window.loaded_url, server.url)
        self.assertIsNotNone(window.loaded_html)
        self.assertIn("LegalMask 启动失败", window.loaded_html)
        self.assertIn("legalmask.log", window.loaded_html)

    def test_loaded_page_remains_open_without_error_fallback(self):
        window = _FakeWindow()
        server = _FakeServer()

        _load_desktop_application(window, server, Path("legalmask.log"))

        self.assertEqual(window.loaded_url, server.url)
        self.assertIsNone(window.loaded_html)


if __name__ == "__main__":
    unittest.main()
