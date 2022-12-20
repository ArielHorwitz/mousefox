
from typing import Optional
from loguru import logger
import kvex as kx
import kvex.kivy
import arrow
import pgnet


LINE_WIDGET_HEIGHT = 40
AUTO_REFRESH_INTERVAL = 1


class ServerFrame(kx.XAnchor):
    def __init__(self, game_widget_class: kvex.kivy.Widget, **kwargs):
        super().__init__(**kwargs)
        self._game_widget_class = game_widget_class
        self._client: Optional[pgnet.BaseClient] = None
        self._next_dir_refresh: arrow.Arrow = arrow.now()
        self.games_dir = dict()
        self.app.menu.add_button("server", "leave_game", self._leave_game)
        self.app.controller.bind("server.leave_game", self._leave_game)
        self.app.controller.bind("server.lobby.focus_create", self._focus_create)
        self.app.controller.bind("server.lobby.focus_list", self._focus_list)
        self.make_widgets()

    def set_client(self, client: pgnet.BaseClient):
        """Set the client to use for this widget."""
        if self._client:
            self._client.on_game = None
        self._client = client
        client.on_game = self.on_game
        self.on_game(client.game)

    def make_widgets(self):
        self.main_frame = kx.XAnchor()
        self.add_widget(self.main_frame)
        self.make_bg(kx.get_color("orange", v=0.3))
        # Game list
        title = kx.XLabel(text="[b]Server lobby[/b]", font_size=18)
        title.set_size(y=LINE_WIDGET_HEIGHT)
        title.make_bg(kx.XColor(v=0, a=0.4))
        self.games_list = kx.XList(
            items=[""],
            selection_color=(1, 1, 1),
            item_height=LINE_WIDGET_HEIGHT,
        )
        self.games_list.bind(
            on_invoke=self._on_game_invoke,
            selection=self._show_game,
        )
        list_frame = kx.XBox(orientation="vertical")
        list_frame.add_widgets(title, self.games_list)

        # Game info
        info_title = kx.XLabel(text="[b]Game Details[/b]")
        info_title.set_size(y=LINE_WIDGET_HEIGHT)
        self.game_info_label = kx.XLabel(halign="left", valign="top", padding=(10, 5))
        join_iwidgets = dict(password=kx.XInputPanelWidget("Password", "password"))
        self.join_panel = kx.XInputPanel(
            join_iwidgets,
            reset_text="",
            invoke_text="Join",
        )
        self.join_panel.bind(on_invoke=self._join_game)
        join_frame = kx.XAnchor.wrap(self.join_panel, x=0.8)
        join_frame.set_size(y=LINE_WIDGET_HEIGHT * 2)
        info_panel = kx.XBox(orientation="vertical")
        info_panel.add_widgets(
            info_title,
            self.game_info_label,
            join_frame,
        )
        info_panel.make_bg(kx.get_color("lime", v=0.3))

        # Create game
        create_title = kx.XLabel(text="[b]Create new game[/b]")
        create_title.set_size(y=LINE_WIDGET_HEIGHT)
        pwidgets = dict(
            name=kx.XInputPanelWidget("Name"),
            password=kx.XInputPanelWidget("Password", "password"),
        )
        self.create_panel = kx.XInputPanel(
            pwidgets,
            invoke_text="Create game",
            reset_text="",
        )
        self.create_panel.bind(on_invoke=self._create_game)
        create_panel_ = kx.XAnchor.wrap(self.create_panel, x=0.8)
        create_panel_.set_size(y=300)
        create_frame = kx.XBox(orientation="vertical")
        create_frame.add_widgets(create_title, create_panel_)
        create_frame.make_bg(kx.get_color("pink", v=0.3))

        # Assemble
        right_frame = kx.XBox(orientation="vertical")
        right_frame.add_widgets(info_panel, create_frame)
        self.lobby_frame = kx.XBox()
        self.lobby_frame.add_widgets(list_frame, right_frame)
        self.show_lobby()

    def show_lobby(self, *args):
        self.main_frame.clear_widgets()
        self.main_frame.add_widget(self.lobby_frame)
        self._refresh_games()
        self._show_game()
        self.games_list.focus = True
        self.app.menu.get_button("server", "leave_game").disabled = True
        self.app.controller.set("server.lobby")

    def make_game(self):
        self.main_frame.clear_widgets()
        game_frame = self._game_widget_class(self._client)
        self.main_frame.add_widget(game_frame)
        self.app.menu.get_button("server", "leave_game").disabled = False
        self.app.controller.set("server.game")

    def update(self):
        if not self._client or not self._client.connected:
            return
        if arrow.now() > self._next_dir_refresh:
            self._next_dir_refresh = arrow.now().shift(seconds=AUTO_REFRESH_INTERVAL)
            self._refresh_games()

    def on_game(self, game: Optional[str]):
        logger.info(f"New game: {game}")
        if game:
            self.make_game()
        else:
            self.show_lobby()

    def _show_game(self, *args, name: str = ""):
        name = self.games_list.items[self.games_list.selection]
        game = self.games_dir.get(name)
        if not game:
            self.game_info_label.text = "No games found. Create a new game."
            self.join_panel.set_showing("password", False)
            return
        users = game.get("users")
        passprot = game.get("password_protected")
        password = "[i]Password protected.[/i]" if passprot else ""
        text = f"[b]{name}[/b]\n\n{users} users in game.\n\n{password}"
        self.game_info_label.text = text
        self.join_panel.set_showing("password", passprot)

    def _create_game(
        self,
        *args,
        name: Optional[str] = None,
        password: Optional[str] = None,
    ):
        if not self._client:
            return
        values = self.create_panel.get_values()
        name = name or values["name"]
        password = password or values["password"] or None
        self._client.create_game(name, password, callback=self._feedback_response)

    def _join_game(self, *args, name: Optional[str] = None):
        if not self._client:
            return
        name = name or self.games_list.items[self.games_list.selection]
        password = None
        game = self.games_dir.get(name)
        if not game:
            return
        if game.get("password_protected"):
            password = self.join_panel.get_value("password")
        self._client.join_game(name, password, callback=self._feedback_response)

    def _leave_game(self, *args):
        if self._client:
            self._client.leave_game(callback=self._feedback_response)

    def _refresh_games(self, *args):
        if self._client:
            self._client.get_games_dir(self._on_games_dir_response)

    def _on_games_dir_response(self, games_dir_response: pgnet.Response):
        self.games_dir = games_dir_response.payload.get("games")
        games = sorted(self.games_dir.keys()) or [""]
        self.games_list.items = games
        self._show_game()

    def _on_game_invoke(self, w, index: int, label: str):
        self._join_game(name=label)

    def _focus_create(self):
        self.create_panel.set_focus("name")

    def _focus_list(self):
        self.games_list.focus = True

    @property
    def in_game(self):
        return self._client and self._client.game is not None

    def _feedback_response(self, response: pgnet.Response):
        if response.status == pgnet.STATUS_OK:
            return
        stypes = {
            pgnet.STATUS_UNEXPECTED: "warning",
            pgnet.STATUS_BAD: "error",
        }
        self.app.set_feedback(response.message, stypes[response.status])
