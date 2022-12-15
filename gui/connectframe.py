
from dataclasses import dataclass
import kex as kx
import pgnet
import logic.client
import util


LINE_HEIGHT = 40
TITLE_TEXT = "[b][u]Welcome to KPdemo[/u][/b]"
INFO_TEXT = (
    "This online multiplayer game of tic-tac-toe is a demo for the Kex and"
    " PGNet Python libraries."
    "\n\n"
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


CONFIG_FILE = util.get_appdata_dir() / "connection_config.txt"


@dataclass
class _ConnectionConfig:
    online: bool = True
    username: str = "guest"
    address: str = "localhost"
    port: int = 38929
    pubkey: str = ""

    @classmethod
    def load_from_disk(cls) -> "_ConnectionConfig":
        try:
            with open(CONFIG_FILE) as f:
                data = f.read()
            online, user, addr, port, pubkey = data.splitlines()
            return cls(bool(online), user, addr, int(port), pubkey)
        except Exception:
            return cls()

    def save_to_disk(self):
        data = [int(self.online), self.username, self.address, self.port, self.pubkey]
        with open(CONFIG_FILE, "w") as f:
            f.write("\n".join(str(d) for d in data))
            f.write("\n")


class ConnectionFrame(kx.Anchor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.make_widgets()
        self.app.controller.bind("connection.start", self._invoke_play_btn)
        self.app.controller.bind(
            "connection.toggle_multiplayer",
            self._toggle_online_checkbox,
        )

    def make_widgets(self):
        self.clear_widgets()
        config = _ConnectionConfig.load_from_disk()
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
        self.online_checkbox = kx.CheckBox(active=config.online)
        self.online_checkbox.bind(active=self._toggle_online)
        online_frame, online_label = _wrap_option(
            self.online_checkbox,
            text="Multiplayer",
        )
        self.username_input = kx.Entry(text=config.username, select_on_focus=True)
        username_frame, username_label = _wrap_option(
            self.username_input,
            text="* Username"
        )
        self.password_input = kx.Entry(text="", select_on_focus=True, password=True)
        password_frame, password_label = _wrap_option(
            self.password_input,
            text="Password"
        )
        self.address_input = kx.Entry(text=config.address, select_on_focus=True)
        address_frame, address_label = _wrap_option(
            self.address_input,
            text="* IP address"
        )
        self.port_input = kx.Entry(text=str(config.port), select_on_focus=True)
        port_frame, port_label = _wrap_option(
            self.port_input,
            text="* Port number"
        )
        self.verify_input = kx.Entry(text=config.pubkey, select_on_focus=True)
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
        main_frame.add(panel_frame, options_frame)
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

    def _toggle_online(self, w, value):
        for w in self.online_options_widgets:
            w.disabled = not value
        self.username_input.focus = True

    def _invoke_play_btn(self, *args):
        online = self.online_checkbox.active
        username = self.username_input.text or None
        address = self.address_input.text
        port = self.port_input.text
        pubkey = self.verify_input.text
        try:
            port = int(port)
            assert 0 < port < 2**16
        except (ValueError, AssertionError):
            self.app.set_feedback_warning("Port number must be a positive integer.")
            return
        if online:
            client = logic.client.Client(
                address=address,
                port=port,
                username=username,
                password=self.password_input.text,
                verify_server_pubkey=pubkey or None,
            )
        else:
            client = logic.client.LocalhostClient(username=username)
        self.app.set_client(client)
        config = _ConnectionConfig(online, username, address, port, pubkey)
        config.save_to_disk()

    def _toggle_online_checkbox(self, *a):
        self.online_checkbox.toggle()
