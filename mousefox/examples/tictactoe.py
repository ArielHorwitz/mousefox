"""Example Tic-tac-toe game for MouseFox.

Provides `APP_CONFIG` dictionary to pass keyword arguments for `mousefox.run`.
"""

from typing import Optional
import arrow
import copy
import json
import random
import pgnet
from pgnet import Packet, Response, Status
import kvex as kx


WINNING_LINES = [
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
]
BLANK_DATA = dict(
    board=[""] * 9,
    players=[],
    x_turn=True,
    in_progress=False,
)
BOT_NAME = "Tictactoe Bot"
BOT_THINK_TIME = 1


class Game(pgnet.Game):
    """Tic-tac-toe game logic."""

    def __init__(self, *args, save_string: Optional[str] = None, **kwargs):
        """Override base method."""
        super().__init__(*args, **kwargs)
        data = json.loads(save_string or json.dumps(BLANK_DATA))
        self._next_bot_turn = arrow.now()
        self.board: list[str] = data["board"]
        self.players: list[str] = data["players"]
        self.x_turn: bool = data["x_turn"]
        self.outcome: str = "Waiting for players."
        if data["in_progress"]:
            self.outcome = "In progress."
        self.in_progress: bool = data["in_progress"]
        self.commands = dict(
            single_player=self._set_single_player,
            play_square=self._play_square,
        )

    @property
    def persistent(self):
        """Override base property."""
        return self.in_progress and any(self.board) and BOT_NAME not in self.players

    def get_save_string(self) -> str:
        """Override base method."""
        data = dict(
            board=self.board,
            players=self.players,
            x_turn=self.x_turn,
            in_progress=self.in_progress,
        )
        return json.dumps(data)

    def user_joined(self, player: str):
        """Override base method."""
        if player not in self.players:
            self.players.append(player)
        if len(self.players) == 2:
            random.shuffle(self.players)
            self.in_progress = True
            self.outcome = "In progress."

    def user_left(self, player: str):
        """Override base method."""
        if player in self.players[2:]:
            self.players.remove(player)

    def handle_game_packet(self, packet: Packet) -> Response:
        """Override base method."""
        meth = self.commands.get(packet.message)
        if not meth:
            return Response("No such command.")
        return meth(packet)

    # Logic
    @property
    def _state_hash(self) -> str:
        data = [
            str(self.board),
            str(self.players),
            str(self.x_turn),
        ]
        final = hash(tuple(data))
        return final

    @property
    def _current_username(self) -> str:
        if not self.in_progress:
            return ""
        return self.players[int(self.x_turn)]

    def _winning_line(
        self,
        board: Optional[list[str]] = None,
    ) -> Optional[tuple[int, int, int]]:
        if board is None:
            board = self.board
        for a, b, c in WINNING_LINES:
            mark = board[a]
            if mark and mark == board[b] == board[c]:
                return a, b, c
        return None

    def _check_progress(self):
        winning_line = self._winning_line()
        if winning_line:
            mark = self.board[winning_line[0]]
            self.in_progress = False
            self.outcome = (f"{self._mark_to_username(mark)} playing as {mark} wins!")
            return
        if all(self.board):
            self.in_progress = False
            self.outcome = "Draw."

    def _mark_to_username(self, mark: str):
        assert mark
        return self.players[0 if mark == "O" else 1]

    def _username_to_mark(self, username: str):
        assert username in self.players[:2]
        return "O" if username == self.players[0] else "X"

    def update(self):
        """Override base method."""
        if self._current_username != BOT_NAME:
            return
        if arrow.now() <= self._next_bot_turn:
            return
        my_mark = self._username_to_mark(BOT_NAME)
        enemy_player_idx = int(not bool(self.players.index(self._current_username)))
        enemy_mark = self._username_to_mark(self.players[enemy_player_idx])
        empty_squares = [s for s in range(9) if not self.board[s]]
        random.shuffle(empty_squares)
        # Find winning moves
        for s in empty_squares:
            new_board = copy.copy(self.board)
            new_board[s] = my_mark
            if self._winning_line(new_board):
                self._do_play_square(s, my_mark)
                return
        # Find losing threats
        for s in empty_squares:
            new_board = copy.copy(self.board)
            new_board[s] = enemy_mark
            if self._winning_line(new_board):
                break
        self._do_play_square(s, my_mark)

    # Commands
    def handle_heartbeat(self, packet: Packet) -> Response:
        """Override base method."""
        state_hash = self._state_hash
        client_hash = packet.payload.get("state_hash")
        if client_hash == state_hash:
            return Response("Up to date.", dict(state_hash=state_hash))
        payload = dict(
            state_hash=state_hash,
            players=self.players,
            board=self.board,
            your_turn=packet.username == self._current_username,
            info=self._get_user_info(packet.username),
            in_progress=self.in_progress,
            winning_line=self._winning_line(),
        )
        return Response("Updated state.", payload)

    def _set_single_player(self, packet: Packet) -> Response:
        if len(self.players) >= 2:
            return Response("Game has already started.", status=Status.UNEXPECTED)
        self.user_joined(BOT_NAME)
        self._next_bot_turn = arrow.now().shift(seconds=BOT_THINK_TIME)
        return Response("Started single player mode.")

    def _play_square(self, packet: Packet) -> Response:
        username = self._current_username
        if packet.username != username or username == BOT_NAME:
            return Response("Not your turn.", status=Status.UNEXPECTED)
        square = int(packet.payload["square"])
        if self.board[square]:
            return Response("Square is already marked.", status=Status.UNEXPECTED)
        self._do_play_square(square, self._username_to_mark(username))
        return Response("Marked square.")

    def _do_play_square(self, square: int, mark: str, /):
        self.board[square] = mark
        self.x_turn = not self.x_turn
        self._check_progress()
        self._next_bot_turn = arrow.now().shift(seconds=BOT_THINK_TIME)

    def _get_user_info(self, username: str) -> str:
        if not self.in_progress:
            return self.outcome
        current_username = self._current_username
        if username not in self.players[:2]:
            mark = self._username_to_mark(current_username)
            return f"{self.outcome}\nSpectating {current_username}'s turn as {mark}"
        turn = "Your turn" if username == current_username else "Awaiting turn"
        return f"{turn}, playing as: {self._username_to_mark(username)}"


class GameWidget(kx.XAnchor):
    """Tic-tac-toe GUI widget."""

    def __init__(self, client: pgnet.Client, **kwargs):
        """Override base method."""
        super().__init__(**kwargs)
        self.client = client
        self._make_widgets()
        self.game_state = dict(state_hash=None)
        client.on_heartbeat = self.on_heartbeat
        client.heartbeat_payload = self.heartbeat_payload

    def on_heartbeat(self, heartbeat_response: pgnet.Response):
        """Update game state."""
        server_hash = heartbeat_response.payload.get("state_hash")
        if server_hash == self.game_state.get("state_hash"):
            return
        self.game_state = heartbeat_response.payload
        new_hash = self.game_state.get("state_hash")
        print(f"New game state (hash: {new_hash})")
        if new_hash:
            self._on_game_state(self.game_state)
        else:
            print(f"Missing state hash: {self.game_state=}")

    def heartbeat_payload(self) -> dict:
        """Send latest known state hash."""
        return dict(state_hash=self.game_state.get("state_hash"))

    def _make_widgets(self):
        self.info_panel = kx.XLabel(halign="left", valign="top", padding=(10, 5))
        self.single_player_btn = kx.XButton(
            text="Start single player",
            on_release=self._single_player,
        )
        spbtn = kx.XAnchor.wrap(self.single_player_btn, x=0.5)
        spbtn.set_size(y=50)
        board_frame = kx.XGrid(cols=3)
        self.board = []
        for i in range(9):
            square = kx.XButton(
                font_size=36,
                background_normal=kx.from_atlas("vkeyboard_key_normal"),
                background_down=kx.from_atlas("vkeyboard_key_down"),
                on_release=lambda *a, idx=i: self._play_square(idx),
            )
            square.background_color = kx.get_color("main").rgba
            self.board.append(square)
            board_frame.add_widget(kx.XAnchor.wrap(square, x=0.85, y=0.85))
        # Assemble
        self.panel_frame = kx.XBox(orientation="vertical")
        self.panel_frame.add_widgets(self.info_panel, spbtn)
        self.panel_frame.set_size(x="350dp")
        main_frame = kx.XBox()
        main_frame.add_widgets(self.panel_frame, board_frame)
        main_frame.make_bg(kx.get_color("second_", v=0.5))
        self.clear_widgets()
        self.add_widget(main_frame)

    def _on_game_state(self, state):
        players = state.get("players", [])[:2]
        spectators = state.get("players", [])[2:]
        info = state.get('info', '')
        if state.get("your_turn"):
            self.panel_frame.make_bg(kx.get_color("primary", v=0.75))
            info = f"[b]{state.get('info', '')}[/b]"
        else:
            self.panel_frame.make_bg(kx.get_color("primary", v=0.5))
        self.info_panel.text = "\n".join([
            "\n",
            info,
            "\n",
            f"[u]Game:[/u] [i]{self.client.game}[/i]",
            "\n",
            "[u]Players:[/u]",
            *(f" ( [b]{'OX'[i]}[/b] ) {p}" for i, p in enumerate(players)),
            "\n",
            "[u]Spectators:[/u]",
            *(f" • {s}" for s in spectators),
        ])
        winning_line = state.get("winning_line") or tuple()
        marks = tuple(str(s or "") for s in state.get("board", [None] * 9))
        for i, (square_btn, mark) in enumerate(zip(self.board, marks)):
            square_btn.text = mark
            winning_square = i in winning_line
            square_btn.bold = winning_square
            text_color = kx.get_color("second" if winning_square else "primary_")
            square_btn.color = text_color.rgba
        self.single_player_btn.disabled = len(state.get("players", "--")) >= 2

    def _play_square(self, index: int, /):
        self.client.send(pgnet.Packet("play_square", dict(square=index)))

    def _single_player(self, *args):
        self.client.send(pgnet.Packet("single_player"), print)


INFO_TEXT = (
    "[b][u]Welcome to MouseFox[/u][/b]"
    "\n\n"
    "This game of Tic-tac-toe is a builtin game example to demo MouseFox."
)
ONLINE_INFO_TEXT = (
    "[u]Connecting to a server[/u]"
    "\n\n"
    "To register (if the server allows it) simply choose a username and password"
    " and log in."
)
APP_CONFIG = dict(
    game_class=Game,
    game_widget=GameWidget,
    title="MouseFox Tic-tac-toe",
    info_text=INFO_TEXT,
    online_info_text=ONLINE_INFO_TEXT,
)


def run():
    """Run tictactoe example."""
    from .. import run

    run(**APP_CONFIG)
