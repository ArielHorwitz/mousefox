""".. include:: ../README.md

# Install
```bash
pip install git+https://github.com/ArielHorwitz/mousefox.git
```

# Built-in examples
Tic-tac-toe:
```python3
import mousefox

mousefox.examples.tictactoe()
```

Text chat:
```python3
import mousefox

mousefox.examples.chat()
```

# Getting started
When working with MouseFox, we will become familiar with
[PGNet](https://github.com/ArielHorwitz/pgnet) and [Kivy](https://kivy.org/doc/stable/).
Let's walk through making a simple multiplayer clicker game.

## Game logic
We require a `pgnet.Game` class. This class will be initialized by the server whenever a
user creates a new game:
```python3
import pgnet

class ClickerGame(pgnet.Game):
    clicks = 0

    def handle_heartbeat(self, packet: pgnet.Packet) -> pgnet.Response:
        # Return game updates
        message = f"Number of clicks: {self.clicks}"
        return pgnet.Response(message)

    def handle_game_packet(self, packet: pgnet.Packet) -> pgnet.Response:
        # Handle requests and actions
        self.clicks += 1
        return pgnet.Response("Clicked.")
```

## Game widget
We require a Kivy `Widget` class. This class will be initialized by the GUI whenever the
user joins a game.
```python3
from kivy.uix.label import Label
import pgnet

class ClickerWidget(Label):
    def __init__(self, client: pgnet.Client):
        # Init the kivy widget and bind to client heartbeat
        super().__init__(text="Waiting for data from server...")
        self.client = client
        self.client.on_heartbeat = self.on_heartbeat

    def on_heartbeat(self, heartbeat: pgnet.Response):
        # Use heartbeat to get game updates
        self.text = heartbeat.message

    def on_touch_down(self, touch):
        # Use client to send requests and do actions
        if self.collide_point(*touch.pos):
            self.client.send(pgnet.Packet("Click"))
```

## Running the app
We can now call `mousefox.run` to run the app:
```python3
import mousefox

mousefox.run(
    game_widget=ClickerWidget,
    game_class=ClickerGame,
)
```

Check out the examples
[source code](https://github.com/ArielHorwitz/mousefox/tree/master/mousefox/examples/).
"""  # noqa: D415


import os
import sys
import asyncio
from loguru import logger
from . import app
from . import examples  # noqa: F401
from . import util  # noqa: F401


def run(**kwargs):
    """Run the app. Takes arguments like `mousefox.AppConfig`.

    See also: `async_run`.
    """
    asyncio.run(async_run(**kwargs))


async def async_run(**kwargs):
    """Coroutine to run the app. Takes arguments like `mousefox.AppConfig`.

    See also: `run`.
    """
    logger.info("Starting MouseFox.")
    config = app.app.AppConfig(**kwargs)
    mf_app = app.app.App(config)
    exit_code = await mf_app.async_run()
    if not config.allow_quit:
        return
    # Restart if exit code is -1
    if exit_code == -1:
        logger.info("Restarting MouseFox...")
        os.execl(sys.executable, sys.executable, *sys.argv)
    logger.info("Closing MouseFox.")
    quit()


AppConfig = app.app.AppConfig
