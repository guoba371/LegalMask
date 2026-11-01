import socket
import unittest

from main import DesktopServer, _find_free_port


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


if __name__ == "__main__":
    unittest.main()
