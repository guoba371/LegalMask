import subprocess
import sys
import unittest
from pathlib import Path


class TempWorkspaceTests(unittest.TestCase):
    def test_temp_directory_is_removed_when_process_exits(self):
        project_root = Path(__file__).resolve().parents[1]
        script = (
            "from core.temp_workspace import make_temp_dir; "
            "print(make_temp_dir('legalmask_test_'))"
        )

        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        temp_dir = Path(completed.stdout.strip().splitlines()[-1])
        self.assertFalse(
            temp_dir.exists(),
            f"Temporary directory was not removed: {temp_dir}",
        )


if __name__ == "__main__":
    unittest.main()
