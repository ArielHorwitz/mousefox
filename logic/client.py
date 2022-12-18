"""Logic client."""

from typing import Optional, Callable
import asyncio
from loguru import logger
import pgnet.client
import pgnet.localhost
import logic.game
import util


HEARTBEAT_INTERVAL = 0.5


class Client(pgnet.client.BaseClient):
    """Subclass of pgnet Client for this game."""

    def __init__(self, *args, on_game_state: Optional[Callable] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.game_state: dict = {"state_hash": ""}
        self.on_game_state = on_game_state

    def queue_update(self, *args, **kwargs):
        self.send(*args, **kwargs)
        self.check_update(do_next=False)

    def check_update(self, *, do_next: bool = True):
        state_hash = self.game_state.get("state_hash")
        self.send(
            pgnet.Packet("check_update", dict(state_hash=state_hash)),
            self._apply_update,
            do_next=do_next,
        )

    def _apply_update(self, response: pgnet.Response):
        server_hash = response.payload.get("state_hash")
        if server_hash == self.game_state.get("state_hash"):
            return
        self.game_state = response.payload
        new_hash = self.game_state.get("state_hash")
        logger.debug(f"New game state (hash: {new_hash})")
        if not new_hash:
            logger.warning(f"Missing state hash: {self.game_state=}")
        if self.on_game_state:
            self.on_game_state(self.game_state)

    async def async_connect(self):
        heartbeat = asyncio.create_task(self._heartbeat())
        await super().async_connect()
        heartbeat.cancel()

    async def _heartbeat(self):
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            if self.connected and self.game:
                self.check_update()


class LocalhostClient(pgnet.localhost.LocalhostClientMixin, Client):
    """Localhost version of `Client`."""

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            game=logic.game.Game,
            server_kwargs=dict(save_file=util.SERVER_SAVE_FILE),
            **kwargs,
        )
