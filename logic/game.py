"""Game logic."""

from typing import Optional
import json
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


def get_blank_save_string() -> dict:
    return json.dumps(dict(
        board=[""] * 9,
        players=[],
        x_turn=True,
    ))


class Game(BaseGame):

    def __init__(self, *args, save_string: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        save_string = save_string or get_blank_save_string()
        data = json.loads(save_string)
        self.board: list[str] = data["board"]
        self.players: list[str] = data["players"]
        self.x_turn: bool = data["x_turn"]
        self.outcome: str = "In progress."
        self.in_progress: bool = False
        self.commands = dict(
            get_state_hash=self.get_state_hash,
            get_full_data=self.get_full_data,
            play_square=self.play_square,
        )

    @property
    def persistent(self):
        return self.in_progress and any(self.board)

    def get_save_string(self) -> str:
        data = dict(
            board=self.board,
            players=self.players,
            x_turn=self.x_turn,
        )
        return json.dumps(data)

    def user_joined(self, player: str):
        if player not in self.players:
            self.players.append(player)
        if len(self.players) >= 2:
            self.in_progress = True

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

    def _check_progress(self):
        for a, b, c in WINNING_LINES:
            mark = self.board[a]
            if mark and mark == self.board[b] == self.board[c]:
                self.in_progress = False
                self.outcome = f"{self._mark_to_username(mark)} playing as {mark} wins!"
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

    # Commands
    def get_state_hash(self, packet: Packet) -> Response:
        r = Response("Current hash", dict(state_hash=self._state_hash))
        return r

    def get_full_data(self, packet: Packet) -> Response:
        payload = dict(
            state_hash=self._state_hash,
            players=self.players,
            board=self.board,
            your_turn=packet.username == self._current_username,
            info=self._get_user_info(packet.username),
        )
        return Response("Full data", payload)

    def play_square(self, packet: Packet) -> Response:
        username = self._current_username
        if packet.username != username:
            return Response("Not your turn.", status=STATUS_UNEXPECTED)
        square = int(packet.payload["square"])
        if self.board[square]:
            return Response("Square is already marked.", status=STATUS_UNEXPECTED)
        self.board[square] = self._username_to_mark(username)
        self.x_turn = not self.x_turn
        self._check_progress()
        return Response("Marked square.")

    def _get_user_info(self, username: str) -> str:
        if not self.in_progress:
            return self.outcome
        current_username = self._current_username
        if username not in self.players[:2]:
            mark = self._username_to_mark(current_username)
            return f"{self.outcome}\nSpectating {current_username}'s turn as {mark}"
        turn = "Your turn" if username == current_username else "Awaiting turn"
        return f"{turn}, playing as: {self._username_to_mark(username)}"
