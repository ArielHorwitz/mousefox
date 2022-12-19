"""Tic-tac-toe client."""

from typing import Optional, Callable
from loguru import logger
import pgnet.client
import pgnet.localhost


class Client(pgnet.client.BaseClient):
    """Networking client."""

    def __init__(self, *args, on_game_state: Optional[Callable] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.game_state: dict = {"state_hash": None}
        self.on_game_state = on_game_state

    def heartbeat(self):
        """Override base method to automatically update game state."""
        self.check_update()

    def check_update(self, *, do_next: bool = True):
        """Check for and apply updates to game state."""
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


class LocalhostClient(pgnet.localhost.LocalhostClientMixin, Client):
    """Localhost version of `Client`."""
    pass
