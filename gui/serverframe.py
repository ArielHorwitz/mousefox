
from typing import Optional
from loguru import logger
import kex as kx
import arrow
import pgnet
import gui.gameframe
import logic.client


LINE_WIDGET_HEIGHT = 40
AUTO_REFRESH_INTERVAL = 5


def _get_entry_frame(widget, text):
    label = kx.Label(text=text, halign="right", padding=(10, 5))
    label.set_size(x=100)
    box = kx.Box()
    box.set_size(x=300)
    box.add(label, widget)
    frame = kx.Anchor()
    frame.set_size(y=LINE_WIDGET_HEIGHT)
    frame.add(box)
    return frame


class ServerFrame(kx.Anchor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._client: Optional[logic.client.Client] = None
        self._next_dir_refresh: arrow.Arrow = arrow.now()
        self.games_dir = dict()
        self.make_bg(kx.get_color("orange", v=0.3))
        self.main_frame = kx.Anchor()
        self.add(self.main_frame)
        self.make_widgets()
        self.app.server_im.register("server.disconnect", self._disconnect, "^+ c")

    def set_client(self, client: Optional[logic.client.Client]):
        if self._client:
            self._client.on_game = None
        self._client = client
        if client:
            client.on_game = self.on_game

    def make_widgets(self):
        # Title
        title = kx.Label(text="[b]Server lobby[/b]", font_size=18)
        # title.set_size(y=LINE_WIDGET_HEIGHT)
        disconnect_btn = kx.Button(text="Disconnect", on_release=self._disconnect)
        # disconnect_btn.set_size()
        refresh_btn = kx.Button(text="Refresh", on_release=self._refresh_games)
        # refresh_btn.set_size()
        title_frame = kx.Box()
        title_frame.set_size(y=LINE_WIDGET_HEIGHT)
        title_frame.add(disconnect_btn, title, refresh_btn)

        # Join game
        self.games_list = kx.List(
            items=[""],
            bg_color=(0, 0, 0, 0.3),
            fg_color=(1, 1, 1, 0.75),
            item_height=LINE_WIDGET_HEIGHT,
        )
        self.games_list.bind(
            on_invoked=self._on_game_invoked,
            selection=self._show_game,
        )
        self.join_password_input = kx.Entry(password=True)
        self.join_password_input.bind(on_text_validate=self._join_game)
        password_input = _get_entry_frame(self.join_password_input, "Password:")
        join_game_btn = kx.Button(text="Join game", on_release=self._join_game)
        join_game_btn.set_size(hx=0.5)
        join_frame = kx.Box()
        join_frame.set_size(y=LINE_WIDGET_HEIGHT)
        join_frame.add(password_input, join_game_btn)
        join_panel = kx.Box(orientation="vertical")
        join_panel.add(title_frame, self.games_list, join_frame)

        # Game info
        self.game_info_label = kx.Label(halign="left", valign="top", padding=(10, 5))
        self.game_info_label.make_bg(kx.XColor(v=0, a=0.1))
        info_title = kx.Label(text="[b]Game Details[/b]")
        info_title.set_size(y=LINE_WIDGET_HEIGHT)
        info_panel = kx.Box(orientation="vertical")
        info_panel.add(info_title, self.game_info_label)
        info_panel.make_bg(kx.get_color("lime", v=0.3))

        # Create game
        create_title = kx.Label(text="[b]Create new game[/b]")
        create_title.set_size(y=LINE_WIDGET_HEIGHT)
        self.create_name_input = kx.Entry()
        self.create_name_input.bind(on_text_validate=self._create_game)
        create_name = _get_entry_frame(self.create_name_input, "Name:")
        self.create_password_input = kx.Entry(password=True)
        self.create_password_input.bind(on_text_validate=self._create_game)
        create_password = _get_entry_frame(self.create_password_input, "Password:")
        new_game_btn = kx.Button(text="Create game", on_release=self._create_game)
        new_game_btn.set_size(y=LINE_WIDGET_HEIGHT)
        create_panel_ = kx.Box(orientation="vertical")
        create_panel_.add(create_title, create_name, create_password, new_game_btn)
        create_height_ = LINE_WIDGET_HEIGHT * (len(create_panel_.children) + 1)
        create_panel_.set_size(x=350, y=create_height_)
        create_panel = kx.Anchor()
        create_panel.add(create_panel_)
        create_panel.make_bg(kx.get_color("pink", v=0.3))

        # Assemble
        right_panel = kx.Box(orientation="vertical")
        right_panel.add(info_panel, create_panel)
        self.lobby_frame = kx.Box()
        self.lobby_frame.add(join_panel, right_panel)
        self.show_lobby()

    def show_lobby(self, *args):
        self.main_frame.clear_widgets()
        self.main_frame.add(self.lobby_frame)
        self._refresh_games()
        self._show_game()
        kx.schedule_once(self.games_list.set_focus, 0.1)  # Dirty hotfix

    def make_game(self):
        self.main_frame.clear_widgets()
        game_frame = gui.gameframe.GameFrame(self._client)
        self.main_frame.add(game_frame)

    def update(self):
        if not self._client or not self._client.connected:
            return
        if arrow.now() > self._next_dir_refresh:
            self._next_dir_refresh = arrow.now().shift(seconds=AUTO_REFRESH_INTERVAL)
            self._refresh_games()

    def on_game(self, game: str):
        logger.info(f"New game: {game}")
        if game:
            self.make_game()
        else:
            self.show_lobby()

    def _show_game(self, *args, name: str = ""):
        name = self.games_list.items[self.games_list.selection]
        game = self.games_dir.get(name)
        if not game:
            self.game_info_label.text = "Create a new game."
            return
        users = game.get("users")
        passprot = game.get("password_protected")
        password = "[i]Password protected.[/i]" if passprot else ""
        text = f"[b]{name}[/b]\n\n{users} users in game.\n\n{password}"
        self.game_info_label.text = text

    def _create_game(
        self,
        *args,
        name: Optional[str] = None,
        password: Optional[str] = None,
    ):
        if not self._client:
            return
        name = name or self.create_name_input.text
        password = password or self.create_password_input.text or None
        self._client.create_game(name, password)

    def _join_game(self, *args, name: Optional[str] = None):
        if not self._client:
            return
        name = name or self.games_list.items[self.games_list.selection]
        password = self.join_password_input.text or None
        self._client.join_game(name, password)

    def _disconnect(self, *args):
        if not self._client:
            return
        self._client.close()
        self.show_lobby()
        self.app.show_connection_screen()

    def _refresh_games(self, *args):
        if self._client:
            self._client.get_games_dir(self._on_games_dir_response)

    def _on_games_dir_response(self, games_dir_response: pgnet.Response):
        self.games_dir = games_dir_response.payload.get("games")
        games = list(self.games_dir.keys()) or [""]
        self.games_list.items = games
        self._show_game()

    def _on_game_invoked(self, w, index: int, label: str):
        self._join_game(name=label)

    @property
    def in_game(self):
        return self._client and self._client.game is not None
