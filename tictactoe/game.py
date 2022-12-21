"""Tic-tac-toe game logic."""

from typing import Optional
import arrow
import copy
import json
import random
from pgnet import BaseGame, Packet, Response, STATUS_UNEXPECTED


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


class Game(BaseGame):
    def __init__(self, *args, save_string: Optional[str] = None, **kwargs):
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
            check_update=self.check_update,
            play_square=self.play_square,
            single_player=self.set_single_player,
        )

    @property
    def persistent(self):
        return self.in_progress and any(self.board) and BOT_NAME not in self.players

    def get_save_string(self) -> str:
        data = dict(
            board=self.board,
            players=self.players,
            x_turn=self.x_turn,
            in_progress=self.in_progress,
        )
        return json.dumps(data)

    def user_joined(self, player: str):
        if player not in self.players:
            self.players.append(player)
        if len(self.players) == 2:
            random.shuffle(self.players)
            self.in_progress = True
            self.outcome = "In progress."

    def user_left(self, player: str):
        if player in self.players[2:]:
            self.players.remove(player)

    def handle_packet(self, packet: Packet) -> Response:
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

    def _handle_bot(self):
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
    def check_update(self, packet: Packet) -> Response:
        self._handle_bot()
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
            winning_line=self._winning_line(),
        )
        return Response("Updated state.", payload)

    def set_single_player(self, packet: Packet) -> Response:
        if len(self.players) >= 2:
            return Response("Game has already started.", status=STATUS_UNEXPECTED)
        self.user_joined(BOT_NAME)
        self._next_bot_turn = arrow.now().shift(seconds=BOT_THINK_TIME)
        return Response("Started single player mode.")

    def play_square(self, packet: Packet) -> Response:
        username = self._current_username
        if packet.username != username or username == BOT_NAME:
            return Response("Not your turn.", status=STATUS_UNEXPECTED)
        square = int(packet.payload["square"])
        if self.board[square]:
            return Response("Square is already marked.", status=STATUS_UNEXPECTED)
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
