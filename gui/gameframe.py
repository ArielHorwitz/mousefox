
import kex as kx
import pgnet
import logic.client


LINE_WIDGET_HEIGHT = 45


class GameFrame(kx.XAnchor):
    def __init__(self, client: logic.client.Client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.make_bg(kx.get_color("pink", v=0.3))
        self.make_widgets()
        self.client.on_game_state = self._on_game_state
        self._on_game_state(self.client.game_state)
        self.client.check_update()
        self.app.controller.bind("server.game.leave", self.client.leave_game)

    def make_widgets(self):
        self.info_panel = kx.XLabel(halign="left", valign="top", padding=(10, 5))
        self.info_panel.make_bg(kx.get_color("cyan", v=0.2))
        leave_btn = kx.XButton(text="Leave game", on_release=self._leave_game)
        leave_btn.set_size(y=LINE_WIDGET_HEIGHT)
        board_frame = kx.XGrid(cols=3)
        self.board = []
        for i in range(9):
            square = kx.XButton(
                font_size=36,
                on_release=lambda *a, idx=i: self._play_square(idx),
            )
            self.board.append(square)
            board_frame.add_widget(square)
        # Assemble
        panel_frame = kx.XBox(orientation="vertical")
        panel_frame.add_widgets(self.info_panel, leave_btn)
        main_frame = kx.XBox()
        main_frame.add_widgets(panel_frame, board_frame)
        self.clear_widgets()
        self.add_widget(main_frame)

    def _on_game_state(self, state):
        players = state.get("players", [])[:2]
        spectators = state.get("players", [])[2:]
        info = state.get('info', '')
        if state.get("your_turn"):
            info = f"[b]{state.get('info', '')}[/b]"
        self.info_panel.text = "\n".join([
            f"[u]Game:[/u] [i]{self.client.game}[/i]\n",
            info,
            "\n",
            f"[u]Players:[/u] {', '.join(players)}",
            "[u]Spectators:[/u]",
            *(f" -- {s}" for s in spectators),
        ])
        marks = tuple(str(s or "_") for s in state.get("board", [None] * 9))
        for square_btn, mark in zip(self.board, marks):
            square_btn.text = mark

    def _play_square(self, index: int, /):
        self.client.send(pgnet.Packet("play_square", dict(square=index)))

    def _leave_game(self, *args):
        self.client.leave_game()
