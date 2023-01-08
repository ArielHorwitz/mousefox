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

    _conpath = "client.user"

    def __init__(self, client: pgnet.client, game_widget_class: kvex.kivy.Widget):
        """Initialize the class with the game widget class."""
        super().__init__()
        self._game_widget_class = game_widget_class
        self._client = client
        self._make_widgets()
        self._client.on_game = self._on_game
        self._on_game(client.game)
        self.app.menu.set_callback("app", "leave_game", self._leave_game)
        self.app.menu.set_callback("app", "lobby", self._show_lobby)
        self.app.menu.set_callback("app", "game", self._show_game)
        self.app.menu.set_callback("app", "admin_panel", self._show_admin)
        self.app.menu.get_button("app", "lobby").disabled = True
        self.app.menu.get_button("app", "game").disabled = True
        self.app.menu.get_button("app", "admin_panel").disabled = True
        self.app.controller.bind(f"{self._conpath}.leave_game", self._leave_game)
        self.app.controller.bind(f"{self._conpath}.show_lobby", self._show_lobby)
        self.app.controller.bind(f"{self._conpath}.show_game", self._show_game)
        self.app.controller.bind(f"{self._conpath}.show_admin", self._show_admin)
        self.app.controller.set_active_callback(self._conpath, self._show_lobby)

    def update(self):
        """Background refresh tasks."""
        menu_get = self.app.menu.get_button
        current = self._sm.current
        disable = not self.app.controller.is_active(self._conpath)
        menu_get("app", "lobby").disabled = current == "lobby" or disable
        menu_get("app", "game").disabled = current == "game" or disable
        menu_get("app", "admin_panel").disabled = current == "admin" or disable
        menu_get("app", "leave_game").disabled = not bool(self._client.game)
        self.lobby_frame.update()

    def _make_widgets(self):
        self.lobby_frame = LobbyFrame(self._client)
        self.admin_frame = AdminFrame(self._client)
        game_placeholder = kx.XPlaceholder(
            label_text="No game in progress.",
            button_text="Return to lobby",
            callback=self._show_lobby,
        )
        self.game_frame = kx.XContainer(game_placeholder)
        self._sm = kx.XScreenManager.from_widgets(dict(
            lobby=self.lobby_frame,
            game=self.game_frame,
            admin=self.admin_frame,
        ))
        self._sm.transition.duration = 0.1
        self.add_widget(self._sm)

    def _switch_screen(self, name: str):
        self._sm.transition.direction = self._sm.screen_direction(name)
        self._sm.current = name
        is_game = name == "game"
        self.app.controller.active = f"{self._conpath}.{name}"
        self.app.game_controller.active = "" if is_game else None

    def _show_admin(self, *args):
        self._switch_screen("admin")

    def _show_lobby(self, *args):
        self._switch_screen("lobby")

    def _show_game(self, *args):
        self._switch_screen("game")

    def _make_game(self):
        game_frame = self._game_widget_class(self._client)
        self.game_frame.content = game_frame
        self._switch_screen("game")

    def _on_game(self, game: Optional[str]):
        logger.info(f"New game: {game}")
        if game:
            self._make_game()
        else:
            self.game_frame.content = None
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
