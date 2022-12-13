"""Game logic."""

from typing import Optional
import json
from pgnet import BaseGame, Packet, Response, STATUS_UNEXPECTED


def get_blank_save_string() -> dict:
    return json.dumps(dict(
        board=[""] * 9,
        players=[],
        x_turn=True,
    ))


class Game(BaseGame):

    persistent = True

    def __init__(self, *args, save_string: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        save_string = save_string or get_blank_save_string()
        data = json.loads(save_string)
        self.board: list[str] = data["board"]
        self.players: list[str] = data["players"]
        self.x_turn: bool = data["x_turn"]
        self.commands = dict(
            get_state_hash=self.get_state_hash,
            get_full_data=self.get_full_data,
            play_square=self.play_square,
        )

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
    def state_hash(self) -> str:
        data = [
            str(self.board),
            str(self.players),
            str(self.x_turn),
        ]
        final = hash(tuple(data))
        return final

    def _get_turn_username(self) -> str:
        if len(self.players) < 2:
            return ""
        return self.players[int(self.x_turn)]

    # Commands
    def get_state_hash(self, packet: Packet) -> Response:
        r = Response("Current hash", dict(state_hash=self.state_hash))
        return r

    def get_full_data(self, packet: Packet) -> Response:
        payload = dict(
            state_hash=self.state_hash,
            players=self.players,
            board=self.board,
            your_turn=packet.username == self._get_turn_username(),
            info=self._get_user_info(packet.username),
        )
        return Response("Full data", payload)

    def play_square(self, packet: Packet) -> Response:
        user = self._get_turn_username()
        if packet.username != user:
            return Response("Not your turn.", status=STATUS_UNEXPECTED)
        square = int(packet.payload["square"])
        if self.board[square]:
            return Response("Square is already marked.", status=STATUS_UNEXPECTED)
        mark = "X" if self.x_turn else "O"
        self.board[square] = mark
        self.x_turn = not self.x_turn
        return Response("Marked square.")

    def _get_user_info(self, username: str) -> str:
        current_username = self._get_turn_username()
        turn = "Your turn" if username == current_username else "Awaiting turn"
        if username == self.players[0]:
            return f"{turn}, playing as: O"
        elif username == self.players[1]:
            return f"{turn}, playing as: X"
        else:
            mark = "X" if self.x_turn else "O"
            return f"Spectating {current_username}'s turn: {mark}"
