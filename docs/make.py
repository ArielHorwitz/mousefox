"""Documentation utilities."""

from typing import Optional
from pathlib import Path
import shutil
import sys
import os
import subprocess
import platform


DEFAULT_OUTPUT_DIR = Path("./docs/docs/")
# Templates
FAVICON_URL = "https://ariel.ninja/mousefox/icon.png"
TEMPLATE_DIR = Path("./docs/templates")
# Project folders
MOUSEFOX_PATH = Path("./mousefox")
KVEX_PATH = Path("../kvex/kvex")
PGNET_PATH = Path("../pgnet/pgnet")
# Project github trees
MOUSEFOX_GITTREE = "https://github.com/ArielHorwitz/mousefox/blob/master/mousefox/"
KVEX_GITTREE = "https://github.com/ArielHorwitz/kvex/blob/master/kvex/"
PGNET_GITTREE = "https://github.com/ArielHorwitz/pgnet/blob/master/pgnet/"


def make_docs(
    output_dir: Optional[Path] = DEFAULT_OUTPUT_DIR,
    delete_existing: bool = False,
    auto_open: bool = False,
    mousefox_path: Path = MOUSEFOX_PATH,
    kvex_path: Path = KVEX_PATH,
    pgnet_path: Path = PGNET_PATH,
):
    """Make documentation.

    Expects to be running from within the mousefox virtual environment. The defaults are
        relative to the mousefox project root.

    Args:
        output_dir: Path to output the docs. If None, will run the docs server.
        delete_existing: Delete contents of output directory before creating docs.
        auto_open: Automatically open docs in browser.
        mousefox_path: Path to mousefox project folder.
        kvex_path: Path to kvex project folder.
        pgnet_path: Path to pgnet project folder.,
    """
    command = "pdoc"
    args = [
        str(mousefox_path),
        str(kvex_path),
        str(pgnet_path),
        "--favicon",
        FAVICON_URL,
        "--docformat",
        "google",
        "--template-directory",
        str(TEMPLATE_DIR),
        "--edit-url",
        f"mousefox={MOUSEFOX_GITTREE}",
        "--edit-url",
        f"kvex={KVEX_GITTREE}",
        "--edit-url",
        f"pgnet={PGNET_GITTREE}",
    ]
    if output_dir:
        args.extend(["-o", str(output_dir)])
        # Delete existing folder if requested
        if delete_existing and output_dir.is_dir():
            shutil.rmtree(output_dir)
        # Create folder if missing
        output_dir.mkdir(parents=True, exist_ok=True)
        # Add a gitignore file to ignore entire docs folder
        with open(output_dir / ".gitignore", "w") as f:
            f.write("**\n")
    if not auto_open:
        args.append("-n")
    print(f"Running subprocess {command!r} with arguments:")
    for a in args:
        print(f"  {a}")
    subprocess.run([command, *args])
    # Copy images
    shutil.copy2(mousefox_path / "icon.png", output_dir / "icon.png")
    shutil.copy2(mousefox_path / "banner.png", output_dir / "banner.png")
    if output_dir and auto_open:
        _popen_path(output_dir / "index.html")


def _popen_path(path):
    """Opens the given path. Method used is platform-dependent."""
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def main():
    """Run `make_docs` with some arguments parsed from command line.

    Will parse command line arguments:
        * `-a` will pass True to `auto_open`
        * `-d` will pass True to `delete_existing`
        * `-s` will run server instead of saving to disk
    """
    print(f"{sys.argv=}")
    kwargs = dict(
        auto_open="-a" in sys.argv,
        delete_existing="-d" in sys.argv,
    )
    if "-s" in sys.argv:
        kwargs["output_dir"] = None
    make_docs(**kwargs)


if __name__ == "__main__":
    main()
