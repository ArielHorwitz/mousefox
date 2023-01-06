"""Home of `ServerFrame`."""

from typing import Optional
from loguru import logger
import kvex as kx
import kvex.kivy
import pgnet
from .lobbyframe import LobbyFrame
from .adminframe import AdminFrame


class ServerFrame(kx.XAnchor):
    """Widget for connected clients.

    Enables interacting with the server lobby and game widget(s).
    """
    def __init__(self, game_widget_class: kvex.kivy.Widget):
        """Initialize the class with the game widget class."""
        super().__init__()
        self._game_widget_class = game_widget_class
        self._client: Optional[pgnet.Client] = None
        self.screen_manager = kx.XScreenManager()
        self.screen_manager.transition.duration = 0.1
        self._dummy_focus = _DummyFocus()  # For unassigning focus when not visible
        self.add_widget(self.screen_manager)

    def set_client(self, client: pgnet.Client):
        """Set the client to use."""
        if self._client:
            self._client.on_game = None
        self._client = client
        self._make_widgets()
        client.on_game = self._on_game
        self._on_game(client.game)

    def _make_widgets(self):
        self.lobby_frame = LobbyFrame(self._client)
        self.admin_frame = AdminFrame(self._client)
        self.game_frame = kx.XAnchor()
        self.screen_manager.clear_widgets()
        self.screen_manager.add_screen("lobby", self.lobby_frame)
        self.screen_manager.add_screen("admin", self.admin_frame)
        self.screen_manager.add_screen("game", self.game_frame)
        self.app.menu.add_button("server", "leave_game", self._leave_game)
        self.app.controller.bind("server.leave_game", self._leave_game)
        self.app.controller.bind("server.lobby.show_admin_panel", self._show_admin)

    def _show_admin(self, *args):
        sdir = self.screen_manager.screen_direction("admin")
        self.screen_manager.transition.direction = sdir
        self.screen_manager.current = "admin"
        self.app.controller.set_active("server.admin")
        self.app.game_controller.set_active(None)
        self.admin_frame.set_focus()

    def _show_lobby(self, *args):
        sdir = self.screen_manager.screen_direction("lobby")
        self.screen_manager.transition.direction = sdir
        self.screen_manager.current = "lobby"
        self.app.menu.get_button("server", "leave_game").disabled = True
        self.app.controller.set_active("server.lobby")
        self.app.game_controller.set_active(None)
        self.lobby_frame.set_focus()

    def _make_game(self):
        self._dummy_focus.focus = True  # Avoid widget interaction when not visible
        self.app.game_controller.set_active("")
        game_frame = self._game_widget_class(self._client)
        self.game_frame.add_widget(game_frame)
        sdir = self.screen_manager.screen_direction("game")
        self.screen_manager.transition.direction = sdir
        self.screen_manager.current = "game"
        self.app.menu.get_button("server", "leave_game").disabled = False
        self.app.controller.set_active("server.game")

    def update(self):
        """Widget background refresh tasks."""
        if not self._client or not self._client.connected:
            return
        if self.lobby_frame.parent:
            self.lobby_frame.update()

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
