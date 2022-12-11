"""Logic client."""

from typing import Optional, Callable
import asyncio
from loguru import logger
import pgnet.client
import pgnet.localhost


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
        self.send(
            pgnet.Packet("get_state_hash"),
            self._check_update_tick,
            do_next=do_next,
        )

    def _check_update_tick(self, state_hash_response: pgnet.Response):
        server_hash = state_hash_response.payload.get("state_hash")
        if server_hash == self.game_state.get("state_hash"):
            return
        logger.debug("Fetching new data...")
        self.send(
            pgnet.Packet("get_full_data"),
            self._apply_update,
            do_next=True,
        )

    def _apply_update(self, data_response: pgnet.Response):
        self.game_state = data_response.payload
        new_hash = self.game_state.get("state_hash")
        logger.debug(f"New game state (hash: {new_hash})")
        if not new_hash:
            logger.warning(f"Missing state hash: {self.game_state=}")
        self.flush_queue()
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
    pass
