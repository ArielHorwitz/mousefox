"""Utitilies subpackage."""

from pathlib import Path
import os
import platform
import tomli


def toml_load(file: os.PathLike) -> dict:
    """Load TOML file as a dictionary."""
    return tomli.loads(file_load(file))


def file_load(file: os.PathLike) -> str:
    """Loads *file* and returns the contents as a string."""
    with open(file, "r") as f:
        d = f.read()
    return d


def file_dump(file: os.PathLike, d: str, clear: bool = True):
    """Saves the string *d* to *file*.
    Will overwrite the file if *clear* is True, otherwise will append to it.
    """
    with open(file, "w" if clear else "a", encoding="utf-8") as f:
        f.write(d)


def get_appdata_dir() -> Path:
    """Return path to the user's app data folder.

    - Windows: `~\\AppData\\Local\\mousefox`
    - Mac OS: `~/Library/Local/mousefox`
    - Linux: `~/.local/share/mousefox`
    """
    if platform.system() == "Windows":
        parts = ["AppData", "Local"]
    elif platform.system() == "Darwin":
        parts = ["Library"]
    else:
        parts = [".local", "share"]
    path = Path.home().joinpath(*parts) / "mousefox"
    path.mkdir(parents=True, exist_ok=True)
    return path


SERVER_SAVE_FILE: Path = get_appdata_dir() / "server-data.json"
