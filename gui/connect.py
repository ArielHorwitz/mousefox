
import kex as kx
import pgnet
import logic.client


LINE_HEIGHT = 50
TITLE_TEXT = "[b][u]Welcome to TicTacToe[/u][/b]"
INFO_TEXT = (
    "[u]Connecting to a server[/u]"
    "\n\n"
    "To register, simply choose a username and password and log in (if the"
    " server allows it)."
    "\n\n"
    "When playing online, fields starting with [b]*[/b] are required."
    "\n\n"
    "Server verification is optional. If set with the public key given by the"
    " server owner, it will verify the server at the address."
    "\n\n"
    f"Default port number is: [i]{pgnet.DEFAULT_PORT}[/i]"
    "\n\n"
    ""
)


class ConnectionFrame(kx.Anchor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.make_widgets()

    def make_widgets(self):
        self.clear_widgets()
        # Side panel
        title_label = kx.Label(text=TITLE_TEXT)
        title_label.set_size(y=LINE_HEIGHT * 2)
        info_label = kx.Label(
            text=INFO_TEXT,
            valign="top",
            halign="left",
            padding=(10, 10),
        )
        play_button = kx.Button(text="Play")
        play_button.bind(on_release=self._invoke_play_btn)
        play_button.set_size(x=200, y=75)
        # Connection details
        online_label = kx.Label(
            text="Multiplayer",
            halign="right",
            padding=(10, 5),
        )
        online_label.set_size(hx=0.01)
        username_label = kx.Label(
            text="* Username",
            italic=True,
            halign="right",
            padding=(10, 5),
        )
        username_label.set_size(hx=0.01)
        password_label = kx.Label(
            text="Password",
            italic=True,
            halign="right",
            padding=(10, 5),
        )
        password_label.set_size(hx=0.01)
        address_label = kx.Label(
            text="* IP address",
            italic=True,
            halign="right",
            padding=(10, 5),
        )
        address_label.set_size(hx=0.01)
        port_label = kx.Label(
            text="* Port number",
            italic=True,
            halign="right",
            padding=(10, 5),
        )
        port_label.set_size(hx=0.01)
        verify_label = kx.Label(
            text="Server verification",
            italic=True,
            halign="right",
            padding=(10, 5),
        )
        verify_label.set_size(hx=0.01)
        self.multiplayer_checkbox = kx.CheckBox(active=True)
        self.multiplayer_checkbox.bind(active=self._toggle_online)
        self.username_input = kx.Entry(text="guest", select_on_focus=True)
        self.password_input = kx.Entry(text="", select_on_focus=True, password=True)
        self.address_input = kx.Entry(text="localhost", select_on_focus=True)
        self.port_input = kx.Entry(text=str(pgnet.DEFAULT_PORT), select_on_focus=True)
        self.verify_input = kx.Entry(select_on_focus=True)
        options_grid = kx.Grid(
            cols=2,
            row_default_height=LINE_HEIGHT,
            row_force_default=True,
            cols_minimum={0: 150},
        )
        options_grid.add(
            online_label,
            self.multiplayer_checkbox,
            username_label,
            self.username_input,
            password_label,
            self.password_input,
            address_label,
            self.address_input,
            port_label,
            self.port_input,
            verify_label,
            self.verify_input,
        )
        # Assemble
        grid_height = LINE_HEIGHT * (len(options_grid.children) // 2 + 1)
        options_grid.set_size(y=grid_height)
        options_frame = kx.Anchor()
        options_frame.add(options_grid)
        play_frame = kx.Anchor()
        play_frame.add(play_button)
        play_frame.set_size(y=150)
        panel_frame = kx.Box(orientation="vertical")
        panel_frame.set_size(x=350)
        panel_frame.add(title_label, info_label, play_frame)
        main_frame = kx.Box()
        main_frame.set_size(x=900, y=700)
        main_frame.add(options_frame, panel_frame)
        main_frame.make_bg(kx.get_color("orange", v=0.3))
        self.add(main_frame)
        self.online_options_widgets = (
            password_label,
            self.password_input,
            address_label,
            self.address_input,
            port_label,
            self.port_input,
            verify_label,
            self.verify_input,
        )
        for w in self.online_options_widgets:
            w.disabled = not self.multiplayer_checkbox.active
        self.username_input.focus = True
        self.app.connection_im.register(
            "Start game",
            self._invoke_play_btn,
            ["enter", "numpadenter", "spacebar"],
        )
        self.app.connection_im.register(
            "Toggle multiplayer",
            self._toggle_multiplayer,
            "^ m",
        )

    def _toggle_online(self, w, value):
        for w in self.online_options_widgets:
            w.disabled = not value
        self.username_input.focus = True

    def _invoke_play_btn(self, *args):
        username = self.username_input.text or None
        online = self.multiplayer_checkbox.active
        if online:
            port = self.port_input.text
            verify_pubkey = self.verify_input.text or None
            try:
                port = int(port)
                assert 0 < port < 2**16
            except (ValueError, AssertionError):
                self.app.set_feedback_warning("Port number must be a positive integer.")
                return
            client = logic.client.Client(
                address=self.address_input.text,
                port=port,
                username=username,
                password=self.password_input.text,
                verify_server_pubkey=verify_pubkey,
            )
        else:
            client = logic.client.LocalhostClient(username)
        self.app.set_client(client)

    def _toggle_multiplayer(self, *a):
        self.multiplayer_checkbox.toggle()
