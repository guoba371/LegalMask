import atexit
import shutil
import tempfile
from pathlib import Path


_TEMP_DIRS: set[Path] = set()


def make_temp_dir(prefix: str = "legalmask_") -> str:
    path = Path(tempfile.mkdtemp(prefix=prefix))
    _TEMP_DIRS.add(path)
    return str(path)


@atexit.register
def _cleanup_temp_dirs() -> None:
    for path in _TEMP_DIRS:
        shutil.rmtree(path, ignore_errors=True)
    _TEMP_DIRS.clear()
