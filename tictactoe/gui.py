"""GUI widget for tic tac toe."""

import kvex as kx
import pgnet
from .client import Client


LINE_WIDGET_HEIGHT = 45
MARKS = "OX"


class GameWidget(kx.XAnchor):
    def __init__(self, client: Client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.make_widgets()
        self.client.on_game_state = self._on_game_state
        self._on_game_state(self.client.game_state)
        self.client.check_update()

    def make_widgets(self):
        self.info_panel = kx.XLabel(halign="left", valign="top", padding=(10, 5))
        self.single_player_btn = kx.XButton(
            text="Start single player",
            on_release=self._single_player,
        )
        spbtn = kx.XAnchor.wrap(self.single_player_btn, x=0.5)
        spbtn.set_size(y=LINE_WIDGET_HEIGHT)
        board_frame = kx.XGrid(cols=3)
        self.board = []
        for i in range(9):
            square = kx.XButton(
                font_size=36,
                background_normal=kx.from_atlas("vkeyboard_key_normal"),
                background_down=kx.from_atlas("vkeyboard_key_down"),
                on_release=lambda *a, idx=i: self._play_square(idx),
            )
            self.board.append(square)
            board_frame.add_widget(kx.XAnchor.wrap(square, x=0.85, y=0.85))
        # Assemble
        self.panel_frame = kx.XBox(orientation="vertical")
        self.panel_frame.add_widgets(self.info_panel, spbtn)
        main_frame = kx.XBox()
        main_frame.add_widgets(self.panel_frame, board_frame)
        self.clear_widgets()
        self.add_widget(main_frame)

    def _on_game_state(self, state):
        players = state.get("players", [])[:2]
        spectators = state.get("players", [])[2:]
        info = state.get('info', '')
        if state.get("your_turn"):
            self.panel_frame.make_bg(kx.get_color("green", v=0.2))
            info = f"[b]{state.get('info', '')}[/b]"
        else:
            self.panel_frame.make_bg(kx.get_color("cyan", v=0.2))
        self.info_panel.text = "\n".join([
            "\n",
            info,
            "\n",
            f"[u]Game:[/u] [i]{self.client.game}[/i]",
            "\n",
            "[u]Players:[/u]",
            *(f" ( [b]{MARKS[i]}[/b] ) {p}" for i, p in enumerate(players)),
            "\n",
            "[u]Spectators:[/u]",
            *(f" • {s}" for s in spectators),
        ])
        winning_line = state.get("winning_line") or tuple()
        marks = tuple(str(s or "") for s in state.get("board", [None] * 9))
        in_progress = state.get("in_progress")
        for i, (square_btn, mark) in enumerate(zip(self.board, marks)):
            square_btn.text = mark
            winning_square = i in winning_line
            square_btn.bold = winning_square
            square_btn.color = (1, 0.2, 0.2) if winning_square else (1, 1, 1)
            square_btn.disabled = False
            color = 0.25, 0.25, 0.25
            if winning_square or in_progress:
                color = 0, 0.1, 0.35
            square_btn.background_color = color
        self.single_player_btn.disabled = len(state.get("players", "--")) >= 2

    def _play_square(self, index: int, /):
        self.client.send(pgnet.Packet("play_square", dict(square=index)))

    def _single_player(self, *args):
        self.client.send(pgnet.Packet("single_player"), print)
