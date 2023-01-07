"""Home of `UserFrame`."""

from typing import Optional
from loguru import logger
import kvex as kx
import kvex.kivy
import pgnet
from .lobbyframe import LobbyFrame
from .adminframe import AdminFrame


class UserFrame(kx.XAnchor):
    """Widget for connected clients.

    Enables interacting with the server lobby and game widget(s).
    """
    def __init__(self, client: pgnet.client, game_widget_class: kvex.kivy.Widget):
        """Initialize the class with the game widget class."""
        super().__init__()
        self._game_widget_class = game_widget_class
        self._client = client
        self._make_widgets()
        self._client.on_game = self._on_game
        self._on_game(client.game)

    def update(self):
        """Background refresh tasks."""
        leave_btn = self.app.menu.get_button("app", "leave_game")
        if self._client.game:
            leave_btn.disabled = False
        else:
            leave_btn.disabled = True
            self.lobby_frame.update()

    def _make_widgets(self):
        self.lobby_frame = LobbyFrame(self._client)
        self.admin_frame = AdminFrame(self._client)
        self.game_frame = kx.XAnchor()
        self._sm = kx.XScreenManager.from_widgets(dict(
            admin=self.admin_frame,
            lobby=self.lobby_frame,
            game=self.game_frame,
        ))
        self._sm.transition.duration = 0.1
        self.add_widget(self._sm)
        self.app.menu.set_callback("app", "leave_game", self._leave_game)
        self.app.controller.bind("client.leave_game", self._leave_game)
        self.app.controller.bind("client.lobby.show_admin_panel", self._show_admin)

    def _show_admin(self, *args):
        self._sm.transition.direction = self._sm.screen_direction("admin")
        self._sm.current = "admin"
        self.app.controller.set_active("client.admin")
        self.app.game_controller.set_active(None)
        self.admin_frame.set_focus()

    def _show_lobby(self, *args):
        self._sm.transition.direction = self._sm.screen_direction("lobby")
        self._sm.current = "lobby"
        self.app.controller.set_active("client.lobby")
        self.app.game_controller.set_active(None)
        self.lobby_frame.set_focus()

    def _make_game(self):
        self.app.game_controller.set_active("")
        game_frame = self._game_widget_class(self._client)
        self.game_frame.add_widget(game_frame)
        self._sm.transition.direction = self._sm.screen_direction("game")
        self._sm.current = "game"
        self.app.controller.set_active("client.game")

    def _on_game(self, game: Optional[str]):
        logger.info(f"New game: {game}")
        if game:
            self._make_game()
        else:
            self._show_lobby()

    def _leave_game(self, *args):
        if not self._client:
            return
        if self._client.game:
            self._client.leave_game(callback=self.app.feedback_response)
        else:
            self._show_lobby()


class _DummyFocus(kx.XFocusBehavior, kx.XLabel):
    pass
