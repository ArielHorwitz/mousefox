"""Game of tic-tac-toe powered by MouseFox."""

import asyncio
import mousefox
from .game import Game
from .client import Client, LocalhostClient


INFO_TEXT = (
    "[b][u]Welcome to MouseFox[/u][/b]"
    "\n\n"
    "This game of tic-tac-toe is a builtin game example to demo MouseFox."
)
ONLINE_INFO_TEXT = (
    "[u]Connecting to a server[/u]"
    "\n\n"
    "To register (if the server allows it) simply choose a username and password"
    " and log in."
)
APP_KWARGS = dict(
    title="MouseFox Tic-Tac-Toe",
    info_text=INFO_TEXT,
    online_info_text=ONLINE_INFO_TEXT,
)


def _get_game_widget():
    """Performs late import to avoid undesireable Kivy import behavior."""
    from .gui import GameWidget

    return GameWidget


def run():
    """Entry point to run this game of tic-tac-toe using MouseFox."""
    asyncio.run(mousefox.run(
        game=Game,
        client=Client,
        localhost=LocalhostClient,
        get_game_widget=_get_game_widget,
        **APP_KWARGS,
    ))
