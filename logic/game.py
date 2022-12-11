"""Game logic."""

from pgnet import BaseGame, Packet, Response, STATUS_UNEXPECTED


class Game(BaseGame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.board = [None] * 9
        self.players: list[str] = []
        self.x_turn: bool = True
        self.started: bool = False
        self._last_state: str = ""
        self.commands = dict(
            get_state_hash=self.get_state_hash,
            get_full_data=self.get_full_data,
            play_square=self.play_square,
        )

    def add_user(self, player: str):
        if player not in self.players:
            self.players.append(player)
        if len(self.players) == 2:
            self.started = True

    def remove_user(self, player: str):
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
            str(self._last_state),
            str(self.players),
            str(self.board),
        ]
        final = hash(tuple(data))
        return final

    def _get_turn_username(self) -> str:
        if not self.started:
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
        if self.board[square] is not None:
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
