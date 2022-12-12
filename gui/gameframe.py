
import kex as kx
import pgnet
import logic.client


LINE_WIDGET_HEIGHT = 45


class GameFrame(kx.FocusBehavior, kx.Anchor):
    def __init__(self, client: logic.client.Client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.make_bg(kx.get_color("pink", v=0.3))
        self.make_widgets()
        self.client.on_game_state = self._on_game_state
        self._on_game_state(self.client.game_state)
        self.client.check_update()

    def make_widgets(self):
        self.info_panel = kx.Label(halign="left", valign="top")
        self.info_panel.make_bg(kx.get_color("cyan", v=0.2))
        leave_btn = kx.Button(text="Leave game", on_release=self._leave_game)
        leave_btn.set_size(y=LINE_WIDGET_HEIGHT)
        board_frame = kx.Grid(cols=3)
        self.board = []
        for i in range(9):
            square = kx.Button(
                font_size=36,
                on_release=lambda *a, idx=i: self._play_square(idx),
            )
            self.board.append(square)
            board_frame.add(square)
        # Assemble
        panel_frame = kx.Box(orientation="vertical")
        panel_frame.add(self.info_panel, leave_btn)
        main_frame = kx.Box()
        main_frame.add(panel_frame, board_frame)
        self.clear_widgets()
        self.add(main_frame)
        self.focus = True

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

    def keyboard_on_key_down(self, w, key_pair, text, mods):
        keycode, key = key_pair
        if key == "escape":
            self.client.leave_game()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.focus = True
        return super().on_touch_down(touch)
