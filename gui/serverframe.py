
from typing import Optional
from loguru import logger
import kex as kx
import pgnet
import gui.gameframe
import logic.client


LINE_WIDGET_HEIGHT = 45


class ServerFrame(kx.Anchor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._client: Optional[logic.client.Client] = None
        self.make_bg(kx.get_color("pink", v=0.3))
        self.main_frame = kx.Anchor()
        self.add(self.main_frame)
        self.make_widgets()
        self.app.server_im.register("Refresh games", self._refresh_games, "f5")

    def set_client(self, client: Optional[logic.client.Client]):
        if self._client:
            self._client.on_game = None
        self._client = client
        if client:
            client.on_game = self.on_game

    def make_widgets(self):
        games_list_title = kx.Label(text="[u][b]Games[/b][/u]")
        games_list_title.set_size(y=LINE_WIDGET_HEIGHT)
        self.games_label = kx.List(items=[""])
        self.games_label.bind(on_invoked=self._on_game_invoked)
        refresh_btn = kx.Button(text="Refresh games", on_release=self._refresh_games)
        refresh_btn.set_size(y=LINE_WIDGET_HEIGHT)
        new_game_btn = kx.Button(text="Join/create game", on_release=self._join_game)
        new_game_btn.set_size(y=LINE_WIDGET_HEIGHT)
        disconnect_btn = kx.Button(text="Disconnect", on_release=self._disconnect)
        disconnect_btn.set_size(y=LINE_WIDGET_HEIGHT)
        self.name_input = kx.Entry()
        self.name_input.set_size(y=LINE_WIDGET_HEIGHT)
        # Assemble
        list_frame = kx.Box(orientation="vertical")
        list_frame.add(games_list_title, self.games_label, refresh_btn)
        game_frame = kx.Box(orientation="vertical")
        game_frame.add(self.name_input, new_game_btn, disconnect_btn)
        self.lobby_frame = kx.Box()
        self.lobby_frame.add(game_frame, list_frame)
        self.show_lobby()

    def show_lobby(self, *args):
        self.main_frame.clear_widgets()
        self.main_frame.add(self.lobby_frame)
        self._refresh_games()

    def make_game(self):
        self.main_frame.clear_widgets()
        game_frame = gui.gameframe.GameFrame(self._client)
        self.main_frame.add(game_frame)

    def on_game(self, game: str):
        logger.info(f"New game: {game}")
        if game:
            self.make_game()
        else:
            self.show_lobby()

    def _join_game(self, *args, name: Optional[str] = None):
        if not self._client:
            return
        game_name = name or self.name_input.text
        self._client.join_game(game_name)

    def _disconnect(self, *args):
        if not self._client:
            return
        self._client.close()
        self.app.show_connection_screen()

    def _refresh_games(self, *args):
        if self._client:
            self._client.get_games_dir(self._on_games_dir_response)

    def _on_games_dir_response(self, games_dir_response: pgnet.Response):
        games_dir = games_dir_response.payload.get("games")
        logger.debug(f"New games directory: {games_dir}")
        games = []
        for name, game in sorted(games_dir.items()):
            p = "(password)" if game.get("password_protected") else ""
            games.append(f"{name} | {game.get('users')} users {p}")
        games = games or [""]
        self.games_label.items = games

    def _on_game_invoked(self, w, index: int, label: str):
        game_name = label.rsplit(" |", 1)[0]
        self._join_game(name=game_name)

    @property
    def in_game(self):
        return self._client and self._client.game is not None
