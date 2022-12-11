
import kex as kx
import pgnet
import logic.client


LINE_HEIGHT = 40
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


def _wrap_option(entry, text):
    frame = kx.Box()
    label = kx.Label(
        text=text,
        italic=True,
        valign="top",
        halign="right",
        padding=(10, 5),
    )
    label.set_size(x=200)
    frame.add(label, entry)
    frame.set_size(y=LINE_HEIGHT)
    return frame, label


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
        self.online_checkbox = kx.CheckBox(active=True)
        self.online_checkbox.bind(active=self._toggle_online)
        online_frame, online_label = _wrap_option(
            self.online_checkbox,
            text="Multiplayer",
        )
        self.username_input = kx.Entry(text="guest", select_on_focus=True)
        username_frame, username_label = _wrap_option(
            self.username_input,
            text="* Username"
        )
        self.password_input = kx.Entry(text="", select_on_focus=True, password=True)
        password_frame, password_label = _wrap_option(
            self.password_input,
            text="Password"
        )
        self.address_input = kx.Entry(text="localhost", select_on_focus=True)
        address_frame, address_label = _wrap_option(
            self.address_input,
            text="* IP address"
        )
        self.port_input = kx.Entry(text=str(pgnet.DEFAULT_PORT), select_on_focus=True)
        port_frame, port_label = _wrap_option(
            self.port_input,
            text="* Port number"
        )
        self.verify_input = kx.Entry(select_on_focus=True)
        verify_frame, verify_label = _wrap_option(
            self.verify_input,
            text="Server verification"
        )
        advanced_label = kx.Label(
            text="Advanced options",
            color=(0.7, 0.7, 0.7),
            italic=True,
        )
        advanced_label.set_size(y=LINE_HEIGHT)
        options_grid = kx.Box(orientation="vertical")
        options_grid.add(
            online_frame,
            username_frame,
            password_frame,
            address_frame,
            advanced_label,
            port_frame,
            verify_frame,
        )
        # Assemble
        grid_height = LINE_HEIGHT * (len(options_grid.children) // 2 + 1)
        options_grid.set_size(hx=0.8, y=grid_height)
        options_frame = kx.Anchor()
        options_frame.add(options_grid)
        play_frame = kx.Anchor()
        play_frame.add(play_button)
        play_frame.set_size(y=150)
        panel_frame = kx.Box(orientation="vertical")
        panel_frame.set_size(x=350)
        panel_frame.add(title_label, info_label, play_frame)
        panel_frame.make_bg(kx.get_color("cyan", v=0.3))
        main_frame = kx.Box()
        main_frame.set_size(x=900, y=700)
        main_frame.add(options_frame, panel_frame)
        main_frame.make_bg(kx.get_color("pink", v=0.3))
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
            w.disabled = not self.online_checkbox.active
        self.username_input.focus = True
        self.app.connection_im.register(
            "Start game",
            self._invoke_play_btn,
            ["enter", "numpadenter", "spacebar"],
        )
        self.app.connection_im.register(
            "Toggle multiplayer",
            self._toggle_online_checkbox,
            "^ m",
        )

    def _toggle_online(self, w, value):
        for w in self.online_options_widgets:
            w.disabled = not value
        self.username_input.focus = True

    def _invoke_play_btn(self, *args):
        username = self.username_input.text or None
        online = self.online_checkbox.active
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

    def _toggle_online_checkbox(self, *a):
        self.online_checkbox.toggle()
