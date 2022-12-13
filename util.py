"""Utitilies subpackage."""

from pathlib import Path
import platform


def get_appdata_dir() -> Path:
    """Return path to the user's app data folder.

    - Windows: `~\\AppData\\Local\\kpdemo`
    - Mac OS: `~/Library/Local/kpdemo`
    - Linux: `~/.local/share/kpdemo`
    """
    if platform.system() == "Windows":
        parts = ["AppData", "Local"]
    elif platform.system() == "Darwin":
        parts = ["Library"]
    else:
        parts = [".local", "share"]
    path = Path.home().joinpath(*parts) / "kpdemo"
    path.mkdir(parents=True, exist_ok=True)
    return path


SERVER_SAVE_FILE = get_appdata_dir() / "server-data.json"
