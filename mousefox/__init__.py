"""MouseFox

Usage: mousefox [-h | --help] [options]
       mousefox server [--p <password>] [options]
       mousefox dev [options]

Options:
  -h, --help                  Show this help and quit
  --debug-args                Show parsed arguments

GUI Options:
  -u, --unmaximize            Do not maximize the window automatically
  -b, --borderless            Remove window border
  --size <size>               Window size in pixels (e.g. `800x600`)
  --offset <offset>           Window offset in pixels (e.g. `200x50`)

Server Options:
  -g, --listen-globally       Listen globally instead of localhost only
  -p, --admin-password <password>
                              Server admin password
  --port <port>               Listen on port number
  --save-file <file>          Set the location of the server save file
  --delete-save-file          Delete the server save file and quit

Dev Options:
  -r, --remote                Connect to a remote server
"""

from typing import Optional, Type, Callable
import os
import sys
import asyncio
import docopt
import functools
import pathlib
import pgnet
import pgnet.devclient
from loguru import logger
from .util import SERVER_SAVE_FILE


async def run(
    *,
    game: Optional[Type[pgnet.BaseGame]] = None,
    client: Optional[Type[pgnet.BaseClient]] = None,
    localhost: Optional[Type[pgnet.LocalhostClient]] = None,
    get_game_widget: Optional[Callable] = None,
    allow_quit: bool = True,
    **app_kwargs,
):
    """Run MouseFox.

    Parses arguments passed to the script to determine mode and configuration.
    See module documentation for details, or run with command line argument
    "--help".

    Args:
        game: Game to use. Required for the server and localhost.
        client: Client class to use. One of client or localhost_client are
            required for the app.
        localhost_client: LocalhostClient class to use. One of client or
            localhost_client are required for the app.
        get_game_widget: Function to get the Kivy widget. See `run_app`
            arguments. Required for the app.
        allow_quit: Allow this function to quit or restart the script.
        app_kwargs: Keyword arguments for the GUI app.
    """
    args = _parse_script_args()
    logger.info("Starting MouseFox.")
    # Resolve task to run
    if args.delete_save_file:
        exit_code = 0
        if args.save_file.is_file():
            args.save_file.unlink()
            logger.info(f"Deleted server save file: {args.save_file!r}")
        else:
            logger.info(f"No server save file to delete: {args.save_file!r}")
    elif args.dev:
        dev_game = None if args.remote else game
        exit_code = await run_devclient(dev_game, save_file=args.save_file)
    elif args.server:
        exit_code = await run_server(
            game,
            listen_globally=args.listen_globally,
            port=args.port,
            admin_password=args.admin_password,
            save_file=args.save_file,
        )
    else:
        wrapped_localhost = None
        if localhost:
            wrapped_localhost = functools.partial(
                localhost,
                game=game,
                server_kwargs=dict(save_file=args.save_file),
            )
        exit_code = await run_app(
            get_game_widget=get_game_widget,
            client_cls=client,
            localhost_cls=wrapped_localhost,
            maximize=args.maximize,
            borderless=args.borderless,
            size=args.size,
            offset=args.offset,
            **app_kwargs,
        )
    await _close_remaining_tasks()
    if not allow_quit:
        return
    # Restart if exit code is -1
    if exit_code == -1:
        logger.info("Restarting MouseFox...")
        os.execl(sys.executable, sys.executable, *sys.argv)
    logger.info("Closing MouseFox.")
    quit()


async def run_devclient(game: Optional[Type[pgnet.BaseGame]] = None, **server_kwargs):
    """Run the devclient.

    By default will run a remote client, unless `game` is passed. If a game
    class is passed will run a localhost client, and will pass keyword arguments
    from `server_kwargs` to the localhost server.
    """
    remote = game is None
    return await pgnet.devclient.async_run(
        remote=remote,
        game=game,
        server_kwargs=server_kwargs,
    )


def run_server(game: Type[pgnet.BaseGame], **server_kwargs):
    """Run the server.

    Args:
        game: Game class to pass to server.
        server_kwargs: Remaining keyword arguments for the `pgnet.BaseServer`
            instance.
    """
    server = pgnet.BaseServer(game, **server_kwargs)
    return server.async_run()


def run_app(get_game_widget: Callable, **app_kwargs):
    """Run the GUI client app.

    Args:
        get_game_widget: Function that returns the Kivy game widget. The reason
            for calling a function is to import Kivy as late as possible
            because of it's behavior when imported.
        app_kwargs: Remaining keyword arguments for the `mousefox.app.App` instance.
    """
    # Late imports because of Kivy's behavior when imported
    from .app.app import App
    import kvex

    game_widget = get_game_widget()
    if not issubclass(game_widget, kvex.kivy.Widget):
        raise ValueError(
            f"get_game_widget must return a {kvex.kivy.Widget},"
            f" instead got: {game_widget}"
        )
    app = App(game_widget=game_widget, **app_kwargs)
    return app.async_run()


def _parse_script_args() -> dict:
    """Parse arguments from command line based on module docstring."""
    args: dict = docopt.docopt(__doc__)
    if args.debug_args:
        print(f"Raw arguments: {sys.argv}")
    args.size = _parse_2dvector(args.size)
    args.offset = _parse_2dvector(args.offset)
    args.maximize = not args.unmaximize
    args.port = int(args.port or pgnet.DEFAULT_PORT)
    if args.save_file:
        args.save_file = pathlib.Path(args.save_file)
    else:
        args.save_file = SERVER_SAVE_FILE
    if args.debug_args:
        print(f"Parsed arguments: {args}")
    return args


def _parse_2dvector(s: Optional[str]) -> Optional[tuple[int, int]]:
    return None if not s else tuple(int(coord) for coord in s.split("x", 1))


async def _close_remaining_tasks(debug: bool = True):
    remaining_tasks = asyncio.all_tasks() - {asyncio.current_task(), }
    if not remaining_tasks:
        return
    for t in remaining_tasks:
        t.cancel()
    if debug:
        logger.debug(
            f"Remaining {len(remaining_tasks)} tasks:\n"
            + "\n".join(f"  -- {t}" for t in remaining_tasks)
        )
    for coro in asyncio.as_completed(list(remaining_tasks)):
        try:
            await coro
        except asyncio.CancelledError:
            removed_tasks = remaining_tasks - asyncio.all_tasks()
            remaining_tasks -= removed_tasks
            if removed_tasks and not debug:
                logger.debug(f"Removed {len(removed_tasks)} tasks: {removed_tasks}")
                logger.debug(
                    f"Remaining {len(remaining_tasks)} tasks:\n"
                    + "\n".join(f"  -- {t}" for t in remaining_tasks)
                )
            continue
