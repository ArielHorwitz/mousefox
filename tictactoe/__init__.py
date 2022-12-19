"""Game of tic-tac-toe powered by MouseFox."""

import asyncio
import mousefox
from .game import Game
from .client import Client, LocalhostClient


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
    ))
