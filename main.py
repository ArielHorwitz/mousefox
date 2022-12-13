"""Multiplayer game.

Usage: multiplayer [-h | --help] [options]
       multiplayer server [--p <password>] [options]
       multiplayer dev [options]

Options:
  -h, --help                  Show this help and quit

GUI Options:
  -u, --unmaximize            Do not maximize the window automatically
  -b, --borderless            Remove window border
  --size <size>               Window size in pixels (e.g. 800x600)
  --offset <offset>           Window offset in pixels (e.g. 200x50)

Server Options:
  -p, --admin-password <password>
                              Must be set to host globally, localhost
                                  only if no password
  --port <port>               Listen on port number
  --delete-saved-data         Delete the server data from disk

Dev Options:
  -r, --remote                Connect to a remote server
"""


import os
import sys
import asyncio
import docopt
import pgnet
import pgnet.devclient
import util
from loguru import logger


async def main():
    """Main script entry point. See module documentation for details."""
    args: dict = docopt.docopt()
    logger.info("Welcome.")
    if args.delete_saved_data:
        _delete_server_file()
    # Resolve task to run
    if args.dev:
        main_coro = _get_devclient_coro(args)
    elif args.server:
        main_coro = _get_server_coro(args)
    else:
        main_coro = _get_app_coro(args)
    # Await exit code
    exit_code = await main_coro
    await _close_remaining_tasks()
    # Restart if exit code is -1
    if exit_code == -1:
        logger.info("Restarting...")
        os.execl(sys.executable, sys.executable, *sys.argv)
    logger.info("Closing.")
    quit()


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


def _delete_server_file():
    save_file = util.SERVER_SAVE_FILE
    if save_file.is_file():
        save_file.unlink()


def _get_devclient_coro(args):
    import logic.game

    return pgnet.devclient.async_run(
        remote=args.remote,
        game=logic.game.Game,
        server_kwargs=dict(save_file=util.SERVER_SAVE_FILE),
    )


def _get_server_coro(args):
    import logic.game

    kw = dict(save_file=util.SERVER_SAVE_FILE)
    if args.port:
        kw["port"] = int(args.port)
    if args.admin_password:
        kw["address"] = ""  # Listen globally
        kw["admin_password"] = args.admin_password
    server = pgnet.BaseServer(logic.game.Game, **kw)
    return server.async_run()


def _get_app_coro(args):
    import gui.app

    kw = dict(
        borderless=args.borderless,
        maximize=not args.unmaximize,
    )
    if args.size:
        kw["size"] = tuple(int(_) for _ in args.size.split("x", 1))
        kw["maximize"] = False
    if args.offset:
        kw["offset"] = tuple(int(_) for _ in args.offset.split("x", 1))
        kw["maximize"] = False
    app = gui.app.App(**kw)
    return app.async_run()


if __name__ == "__main__":
    asyncio.run(main())
