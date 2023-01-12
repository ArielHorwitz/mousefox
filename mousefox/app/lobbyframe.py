"""Home of `LobbyFrame`."""

from typing import Optional
import arrow
import kvex as kx
import pgnet


LINE_WIDGET_HEIGHT = 40
AUTO_REFRESH_INTERVAL = 1


class LobbyFrame(kx.XAnchor):
    """Widget for interacting with the server lobby."""

    _conpath = "client.user.lobby"

    def __init__(self, client: pgnet.Client):
        """Initialize the class."""
        super().__init__()
        self._client = client
        self._next_dir_refresh: arrow.Arrow = arrow.now()
        self.game_dir = dict()
        self._make_widgets()
        self.app.controller.bind(f"{self._conpath}.focus", self._focus_list)
        self.app.controller.bind(f"{self._conpath}.focus_create", self._focus_create)
        self.app.controller.bind(f"{self._conpath}.focus_list", self._focus_list)
        self.app.controller.set_active_callback(self._conpath, self._focus_list)

    def update(self):
        """Priodically refresh game directory."""
        if not self.app.controller.is_active(self._conpath):
            return
        if not self._client.connected:
            return
        if arrow.now() < self._next_dir_refresh:
            return
        self._next_dir_refresh = arrow.now().shift(seconds=AUTO_REFRESH_INTERVAL)
        self._refresh_games()

    def on_parent(self, w, parent):
        """Refresh when shown."""
        if parent:
            self._refresh_games()
            self._show_game()
            self.games_list.focus = True

    def _make_widgets(self):
        # Game list
        with self.app.subtheme_context("secondary"):
            title = kx.fwrap(kx.XLabel(text="[b]Server lobby[/b]", font_size="18sp"))
            title.set_size(y=LINE_WIDGET_HEIGHT)
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
        join_iwidgets = dict(password=kx.XInputPanelWidget("Password", "password"))
        with self.app.subtheme_context("secondary"):
            info_title = kx.XLabel(text="[b]Game Details[/b]")
            info_title.set_size(y=LINE_WIDGET_HEIGHT)
            self.game_info_label = kx.XLabel(halign="left", valign="top")
            self.join_panel = kx.XInputPanel(
                join_iwidgets,
                reset_text="",
                invoke_text="Join",
            )
            self.join_panel.bind(on_invoke=self._join_game)
            self.join_panel.set_size(y=LINE_WIDGET_HEIGHT * 2)
            info_panel = kx.XBox(orientation="vertical")
            info_panel.add_widgets(
                info_title,
                self.game_info_label,
                self.join_panel,
            )
            info_panel = kx.fpwrap(info_panel)

        # Create game
        pwidgets = dict(
            name=kx.XInputPanelWidget("Name"),
            password=kx.XInputPanelWidget("Password", "password"),
        )
        with self.app.subtheme_context("accent"):
            create_title = kx.XLabel(text="[b]Create new game[/b]")
            create_title.set_size(y=LINE_WIDGET_HEIGHT)
            self.create_panel = kx.XInputPanel(
                pwidgets,
                invoke_text="Create game",
                reset_text="",
            )
            self.create_panel.bind(on_invoke=self._create_game)
            create_panel_ = kx.fpwrap(self.create_panel)
            create_panel_.set_size(y="200dp")
        create_frame = kx.XBox(orientation="vertical")
        create_frame.add_widgets(create_title, create_panel_)

        # Assemble
        right_frame = kx.XBox(orientation="vertical")
        right_frame.add_widgets(info_panel, create_frame)
        main_frame = kx.XBox()
        main_frame.add_widgets(list_frame, right_frame)
        self.add_widget(main_frame)

    def _create_game(self, *args):
        values = self.create_panel.get_values()
        name = values["name"]
        password = values["password"]
        self._client.create_game(
            name,
            password=password,
            callback=self.app.feedback_response,
        )

    def _join_game(self, *args, name: Optional[str] = None):
        name = name or self.games_list.items[self.games_list.selection]
        password = None
        game = self.game_dir.get(name)
        if not game:
            return
        if game.get("password_protected"):
            password = self.join_panel.get_value("password")
        self._client.join_game(
            name,
            password=password,
            callback=self.app.feedback_response,
        )

    def _refresh_games(self, *args):
        self._client.get_game_dir(self._on_game_dir_response)

    def _on_game_dir_response(self, game_dir_response: pgnet.Response):
        self.game_dir = game_dir_response.payload.get("games") or dict()
        games = sorted(self.game_dir.keys()) or [""]
        self.games_list.items = games
        self._show_game()

    def _on_game_invoke(self, w, index: int, label: str):
        self._join_game(name=label)

    def _show_game(self, *args, name: str = ""):
        name = self.games_list.items[self.games_list.selection]
        game = self.game_dir.get(name)
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

    def _focus_create(self):
        self.create_panel.set_focus("name")

    def _focus_list(self):
        self.games_list.focus = True

    set_focus = _focus_list
